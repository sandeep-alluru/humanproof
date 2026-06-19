# Case Study: Separating Real Users from AI Agents in Web Analytics

## Company Profile

**Veridian Analytics** is a web analytics SaaS company with 25 engineers serving 500
e-commerce clients. Their platform tracks real user behavior — click patterns, scroll depth,
time-on-page, funnel progression — to help clients make product decisions. Their stack is
FastAPI (backend), React (dashboard), ClickHouse (event warehouse), and Kafka (event streaming).
They process roughly 80 million page interaction events per day.

## The Problem

An audit in Q3 2024 revealed that 28% of their clients' tracked "user" sessions were generated
by non-human agents. The bot traffic came from three sources:

1. **AI computer-use agents** (Claude computer use, GPT-4o Agents, custom Selenium frameworks)
   used by clients' own QA teams for automated testing, which were inadvertently recorded as
   real sessions.
2. **Competitor price scrapers** that browsed product pages at human-like speeds to extract
   pricing data.
3. **SEO monitoring bots** that clicked through to inflate traffic numbers.

The consequences were severe: a major client had restructured their entire checkout funnel based
on data that was 31% bot-generated, discovering the flaw only after a $200K redesign showed
no improvement in real conversions.

Standard defenses had failed:
- **IP blocklists**: The scrapers rotated residential IPs, indistinguishable from real users.
- **CAPTCHA**: The AI computer-use agents solved CAPTCHAs with >95% success.
- **User-agent filtering**: Modern Selenium forks report authentic browser signatures.
- **Behavioral rate-limiting**: The bots mimicked human browsing speed by adding random delays.

What the bots couldn't fake was mouse trajectory physics. Human mouse movements exhibit
stochastic micro-corrections, velocity fluctuations, and reversals that emerge from motor-neuron
firing patterns. AI agents producing smooth Bezier-curve mouse paths had a distinct, measurable
signature in the `noise_ratio`, `correction_rate`, and `smoothness` features.

## Solution Architecture

```
Browser Client          Veridian Ingest Layer            Analytics Pipeline
--------------          ---------------------            ------------------
mousemove events ──>  [trajectory_buffer.js]                    │
                              │                                   │
                       [POST /track_session]                      │
                              │                                   │
                    [humanproof FastAPI middleware]                │
                              │                                   │
                    [batch_score(trajectories)]                    │
                              │                                   │
                    score >= 0.4? ──yes──>  [real_events_topic] ──> ClickHouse
                              │                                   │
                    score < 0.4?  ──yes──>  [shadow_ban]          │
                                             quarantine_topic ──> QuarantineDB
                                             (bot gets 200 OK,
                                              data silently
                                              quarantined)
```

Veridian added a 50-event mouse trajectory buffer to their client-side JavaScript SDK.
When a session's trajectory buffer fills, it is sent alongside the normal analytics payload.
The humanproof middleware scores the trajectory before the event is written to ClickHouse.

Sessions scoring below 0.4 are shadow-banned: the analytics API returns a normal 200 response
so the bot does not know it has been detected, but the events are written to a separate
`quarantine` topic rather than the main analytics stream. This prevents scrapers from adapting
their behavior in response to detection.

The calibration module was trained on confirmed human sessions (users who completed a purchase
checkout — a reliable human signal) versus confirmed bot sessions (Veridian's own test suite,
captured in a staging environment).

## Implementation

```python
from fastapi import FastAPI, Request
from humanproof import (
    InputSample,
    InputTrajectory,
    MotorScorer,
    batch_score,
    calibrate,
    apply_calibration,
    CalibrationResult,
)
import json

app = FastAPI()

# Load pre-built calibration (trained on confirmed human checkout sessions
# vs. confirmed bot sessions from internal test suite)
with open("calibration.json") as f:
    cal_data = json.load(f)

# Re-hydrate calibration from stored thresholds
scorer = MotorScorer(
    human_threshold=cal_data["human_threshold"],
    ai_threshold=cal_data["ai_threshold"],
)

BOT_SCORE_THRESHOLD = 0.40   # below this: shadow-ban

def parse_trajectory(raw: dict) -> InputTrajectory:
    """Convert client-side mousemove payload to InputTrajectory."""
    samples = [
        InputSample(
            dx=evt["dx"],
            dy=evt["dy"],
            dt=evt["dt"],
            timestamp=evt.get("ts"),
        )
        for evt in raw["events"]
        if evt["dt"] > 0
    ]
    return InputTrajectory(
        samples=samples,
        session_id=raw["session_id"],
    )

@app.post("/track_session")
async def track_session(request: Request):
    body = await request.json()
    trajectory_payload = body.get("trajectory")

    is_bot = False
    human_score = 1.0

    if trajectory_payload and len(trajectory_payload.get("events", [])) >= 10:
        traj = parse_trajectory(trajectory_payload)
        result = scorer.score(traj)
        human_score = result.human_score
        is_bot = human_score < BOT_SCORE_THRESHOLD

    # Route to real analytics or quarantine
    event_topic = "quarantine" if is_bot else "real_events"
    await write_to_kafka(event_topic, {
        **body["analytics"],
        "_humanproof_score": human_score,
        "_is_bot": is_bot,
    })

    # Always return 200 — shadow ban: bots don't know they're quarantined
    return {"status": "ok"}

# Weekly calibration refresh against fresh confirmed sessions
def refresh_calibration(
    confirmed_human_sessions: list[InputTrajectory],
    confirmed_bot_sessions: list[InputTrajectory],
) -> CalibrationResult:
    human_scores = [scorer.score(t).human_score for t in confirmed_human_sessions]
    bot_scores = [scorer.score(t).human_score for t in confirmed_bot_sessions]
    return calibrate(human_scores, bot_scores)
```

## Results

| Metric | Before | After |
|---|---|---|
| Bot traffic in analytics | 28% of all sessions | <1.7% (correctly quarantined) |
| Bot sessions correctly quarantined | 0% | 94% |
| Legitimate user false positive rate | N/A | 1.2% |
| Clients with clean analytics data | 0% (unknown contamination) | 500 (6 months clean) |
| Client decisions made on bot data | Ongoing | Zero since deployment |
| QA time spent on bot cleanup | 3 days/month per client | 0 |

The shadow-ban approach was critical: the first 2 weeks after deployment, Veridian observed
bot operators testing their scrapers against the API. Because the API returned identical
200 responses, the operators concluded their scrapers still worked and did not attempt to
adapt their mouse trajectories. The quarantine database accumulated 14 million bot events
in 6 months — data that would previously have poisoned client dashboards.

## Key Takeaways

- The shadow-ban pattern (return 200, silently quarantine) prevents adversarial adaptation —
  bots never learn they are detected and don't try to improve their trajectory generation.
- `calibrate()` trained on checkout completions (confirmed human) vs. test-suite runs
  (confirmed bot) produced far tighter thresholds than humanproof's defaults, lowering
  the false positive rate from an estimated 4% to 1.2%.
- The 50-event trajectory buffer from the JS SDK provides enough samples for reliable scoring
  without perceptible latency — scoring runs in <5ms on a standard FastAPI worker.
- `MotorScorer` parameters `human_threshold` and `ai_threshold` accept the calibrated values
  directly, making the calibration portable across deployments.
- For SaaS analytics, it is better to quarantine suspicious sessions than block them — blocking
  risks breaking real users on mobile or accessibility devices, while quarantine is reversible.

## Try It Yourself

```bash
pip install "humanproof[api]"

# Start the REST scoring server
uvicorn humanproof.api:app --reload

# Score a trajectory via REST
curl -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{"samples": [{"dx": 0.1, "dy": 0.05, "dt": 10.0}]}'

# Batch score from a directory
humanproof batch ./session_replays/
```
