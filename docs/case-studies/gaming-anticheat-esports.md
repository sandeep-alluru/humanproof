# Case Study: Behavioral Anti-Cheat for Competitive Esports

## Company Profile

**IronLadder** is a competitive gaming platform with 80 engineers that hosts esports tournaments
for 2 million registered players. Their flagship title is a tactical shooter where prize pools
reach $50,000 per tournament. Their tech stack is Python (backend), Go (game server), PostgreSQL
(player data), and Redis (leaderboards). Ranked matches generate roughly 500,000 input trajectory
files per day from game client replays.

## The Problem

Twelve percent of IronLadder's top-1000 ranked players were discovered to be using aimbots or
input macros after a wave of community complaints. Manual review of replays was taking QA staff
4–6 hours per suspect. Traditional anti-cheat approaches had already failed them:

- **Memory scanning** (VAC-style): Cheat software ran on a separate hardware device that
  injected inputs over USB, leaving zero memory footprint on the game process.
- **Statistical outlier detection**: Human professionals also have unusually high accuracy, so
  raw accuracy metrics produced a 22% false positive rate, making bans unenforceable.
- **IP and hardware bans**: Evaded within hours through VPNs and alternate accounts.

The cheats shared a specific signature: perfectly smooth trajectories with near-zero jitter and
no micro-corrections — mathematically impossible for human motor control. IronLadder needed a
behavioral approach that worked from the game client replay data they already collected, with no
kernel driver or hardware access.

Their secondary problem was mid-match aimbot activation. Players had learned to play legitimately
for the first 10 minutes of a match to "warm up" their human score, then activate the cheat for
clutch rounds. A session-unaware scorer would see an averaged score and miss the activation
entirely.

## Solution Architecture

```
Game Client                  Anti-Cheat Pipeline                  Enforcement
-----------                  ----------------------                -----------
replay.json  ──(upload)──>  [session_ingest.py]                      │
                                    │                                  │
                             [analyze_session()]   ──shift_at──>  [ban_queue]
                                    │                                  │
                             [batch_score()]                     [manual_review]
                                    │                                  │
                             [MotorScorer]                       [account_flag]
                             noise_ratio                               │
                             correction_rate                    [shadow_ban]
                             smoothness                               │
                                    │                           [prize_strip]
                             score < 0.4? ──yes──>  [flag]
                             shift detected? ──yes──>  [flag]
```

Replay files from each game client are uploaded at match end. A Celery worker calls
`analyze_session()` on the full trajectory list for that session. Sessions with
`behavioral_shift_detected=True` are immediately queued for automated ban regardless of the
mean score — this catches the "play human, then cheat" pattern directly.

The `calibrate()` function was run once against 10,000 labeled sessions (5,000 confirmed human
from bronze-rank players, 5,000 confirmed bot from a controlled test environment) to set the
decision thresholds. The result was stored and passed as `apply_calibration()` on every scoring
call.

## Implementation

```python
import json
from pathlib import Path
from humanproof import (
    InputSample,
    InputTrajectory,
    MotorScorer,
    batch_score,
    analyze_session,
    detect_shift,
    calibrate,
    apply_calibration,
    CalibrationResult,
)

# Load replay data from a single match session
def load_session_trajectories(replay_dir: Path) -> list[InputTrajectory]:
    trajectories = []
    for replay_file in sorted(replay_dir.glob("*.json")):
        data = json.loads(replay_file.read_text())
        samples = [
            InputSample(dx=s["dx"], dy=s["dy"], dt=s["dt"])
            for s in data["samples"]
        ]
        traj = InputTrajectory(
            samples=samples,
            session_id=data["session_id"],
        )
        trajectories.append(traj)
    return trajectories

# One-time calibration against labeled human/bot sessions
def build_calibration(human_sessions, bot_sessions) -> CalibrationResult:
    scorer = MotorScorer()
    human_scores = [scorer.score(t).human_score for t in human_sessions]
    bot_scores = [scorer.score(t).human_score for t in bot_sessions]
    return calibrate(human_scores, bot_scores)

# Per-session analysis — runs after every completed match
def analyze_match(session_id: str, replay_dir: Path, cal: CalibrationResult) -> dict:
    trajectories = load_session_trajectories(replay_dir)

    # Detect behavioral shift (aimbot activation mid-match)
    analysis = analyze_session(session_id, trajectories)

    # Apply calibration to adjust scoring thresholds
    batch_result = batch_score(trajectories)
    adjusted = apply_calibration(batch_result, cal)

    flag_for_ban = (
        analysis.behavioral_shift_detected          # mid-session activation
        or analysis.verdict == "consistent_ai"      # session-wide bot pattern
        or adjusted.mean_human_score < 0.35         # calibrated threshold
    )

    return {
        "session_id": session_id,
        "verdict": analysis.verdict,
        "risk_level": analysis.risk_level,
        "shift_at_trajectory": analysis.shift_at_index,
        "mean_human_score": analysis.mean_human_score,
        "flagged_count": batch_result.ai_count,
        "ban_recommended": flag_for_ban,
    }

# Batch processing — runs hourly on 50,000 trajectories
def hourly_ban_sweep(session_dirs: list[Path], cal: CalibrationResult):
    results = []
    for session_dir in session_dirs:
        session_id = session_dir.name
        result = analyze_match(session_id, session_dir, cal)
        if result["ban_recommended"]:
            results.append(result)
    return results
```

## Results

| Metric | Before | After |
|---|---|---|
| Cheaters detected (month 1) | Manual, ~20/week | 847 automated bans |
| Ban rate (top-ranked players) | 0% automated | 8.4% |
| False positive rate | 22% (accuracy-based) | 0.3% |
| Mid-session aimbot detection | Not possible | <200ms latency |
| QA hours per suspect | 4–6 hours | 0 (automated) |
| Players protected | 2M | 2M |

The false positive rate dropped from 22% to 0.3% because humanproof measures motor-noise
signatures rather than raw accuracy. Professional players have high accuracy but still show
human noise patterns (`noise_ratio` 0.4–0.8, `correction_rate` 0.15–0.35). The calibration
module allowed IronLadder to tune thresholds against their specific player population rather than
using generic defaults.

## Key Takeaways

- `analyze_session()` is essential for catching mid-match aimbot activation — session-averaged
  scoring alone misses players who "warm up" before enabling the cheat.
- The calibration step is the difference between a 22% and 0.3% false positive rate. Running
  `calibrate()` against your own labeled dataset is worth the effort.
- `batch_score()` processes 50,000 trajectories per hour on a single 8-core worker — no GPU
  or ML infrastructure required.
- humanproof's pure-Python, zero-dependency design meant the entire pipeline deployed in the
  existing Celery/Python infrastructure without a new service.
- The `behavioral_shift_detected` flag in `SessionAnalysis` is the highest-confidence ban signal
  — it corresponds to an abrupt, statistically significant change mid-session.

## Try It Yourself

```bash
pip install humanproof

# Score a single trajectory
humanproof score examples/trajectory.json

# Batch score a directory of replays
humanproof batch ./replays/

# Run the end-to-end demo
python examples/demo.py
```
