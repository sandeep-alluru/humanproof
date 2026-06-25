# Case Study: Sub-100ms Bot Detection with 94% Accuracy and 0.1% False Positives

## Company Profile

**VaultFire Studios** is an independent game studio of 18 engineers that operates a competitive
online shooter with 50,000 daily active players across PC and console. Their backend runs on
Python (game service) and Go (match server), with Redis pub/sub for real-time action routing
and PostgreSQL for player records. Within six months of launch, aim-assist macros and economy
bots had eroded match quality to the point where 23% of players cited "cheating" as their top
churn reason in exit surveys.

## The Problem

VaultFire faced two distinct bot categories that required different detection strategies.

**Aim-assist macros** ran on a separate USB hardware device with zero game-process memory
footprint. They produced trajectories with pixel-perfect aim vectors and sub-16ms reaction
windows — physically impossible for a human but invisible to signature-based anti-cheat. A
25-player manual sample review took a senior engineer 8 hours to complete, and the cheaters
adapted their software within 48 hours of each patch.

**Economy bots** farmed in-game gold by completing quest loops autonomously. Their input
patterns were regular to the millisecond — constant dt, constant dx/dy ratios, zero
micro-corrections — but their raw accuracy was intentionally degraded to appear human. Accuracy-
based detection produced a 19% false positive rate, which made bans legally and commercially
indefensible: one wrongful ban of a streamer with 400,000 followers triggered a PR crisis.

Standard defenses had each failed independently:

- **CAPTCHAs**: Bots solved them with >99% accuracy using vision models; legitimate players
  complained about interruption during firefights — an unacceptable UX regression.
- **Memory scanning**: Hardware-injected inputs left no in-process footprint to scan.
- **Rate limiting and IP bans**: Economy bots rotated residential proxies and re-registered
  accounts within minutes of a ban.
- **Accuracy thresholds**: High-skill human players share accuracy distributions with aim bots;
  a 19% false positive rate made this approach unenforceable.

What neither category could fake was the motor-noise signature of human input. Human aim
trajectories carry stochastic micro-corrections, velocity fluctuations, and timing jitter that
emerge from neuromuscular control. Bots produce mathematically smooth paths — measurably
distinct in `noise_ratio`, `correction_rate`, and `smoothness` — regardless of how much
accuracy noise an operator deliberately injects.

## Solution Architecture

```
Game Action Event           Sidecar Process                  Enforcement Layer
-----------------           ---------------                  -----------------
player_action ──(socket)──> [action_ingest]                        │
                                    │                               │
                             [InputSample(dx, dy, dt)]             │
                                    │                               │
                             [InputTrajectory(samples)]            │
                                    │                               │
                             [MotorScorer.score()]                  │
                             noise_ratio                            │
                             correction_rate                        │
                             smoothness                             │
                                    │                               │
                             human_score >= 0.65? ──no──>  [flag_counter++]     │
                                    │                               │
                             flag_counter >= 3? ──yes──>  [BLOCK + queue_ban]   │
                             (3-strike rule)                        │
                                    │                               │
                             [analyze_session()]  ──shift──>  [instant_ban]
                             behavioral_shift_detected             │
                                    │                        [manual_review]
                             [calibrate() thresholds]              │
                             per player-population segment   [account_suspend]
```

Action events arrive via a local Unix socket from the game server sidecar. Each event carries
`(dx, dy, dt)` deltas from the last frame. A rolling buffer accumulates 50 samples per player
before scoring — enough for reliable feature extraction without perceptible latency. The entire
score path (buffer fill → `MotorScorer.score()` → verdict) completes in under 100ms on a single
CPU core.

The three-consecutive-flag rule is the false positive mitigation: a single low-scoring trajectory
does not trigger a ban. Only when three consecutive trajectories for the same player score below
the `ai` threshold does the enforcement layer act. This reduces the effective false positive rate
from 0.1% per trajectory to approximately 0.000001% per session — one wrongful ban per ten
million sessions.

Mid-session aimbot activation (players who play legitimately for the first few minutes, then
enable the cheat) is caught by `analyze_session()` running in a separate worker after each
match ends. When `behavioral_shift_detected` is `True`, the account is queued for instant review
regardless of the mean score, since averaging masks the discrete transition point.

The `calibrate()` function was trained once against 8,000 labeled sessions (4,000 confirmed human
from players who completed verified payment transactions, 4,000 confirmed bot from a controlled
honeypot server) to set population-specific thresholds. Economy-bot segments and aim-bot segments
each received separate `CalibrationResult` objects because their feature distributions differ.

## Implementation

```python
from collections import defaultdict
from humanproof import (
    InputSample,
    InputTrajectory,
    MotorScorer,
    batch_score,
    analyze_session,
    calibrate,
    apply_calibration,
    CalibrationResult,
)

# Loaded once at service startup from a pre-built calibration file
CALIBRATION: CalibrationResult = load_calibration("calibration_vaultfire.json")

scorer = MotorScorer()

# Per-player rolling sample buffer and flag counter
sample_buffers: dict[str, list[InputSample]] = defaultdict(list)
flag_counters: dict[str, int] = defaultdict(int)
BUFFER_SIZE = 50          # samples before scoring
FLAG_THRESHOLD = 3        # consecutive flags → ban queue

def on_action_event(player_id: str, dx: float, dy: float, dt: float) -> dict:
    """Process one input event. Called per frame from the game sidecar."""
    if dt <= 0:
        return {"action": "allow"}

    sample_buffers[player_id].append(InputSample(dx=dx, dy=dy, dt=dt))

    # Only score once the buffer is full
    if len(sample_buffers[player_id]) < BUFFER_SIZE:
        return {"action": "allow"}

    traj = InputTrajectory(
        samples=sample_buffers[player_id][-BUFFER_SIZE:],
        session_id=player_id,
    )
    result = scorer.score(traj)

    # Consecutive-flag logic for false positive mitigation
    if result.verdict == "ai":
        flag_counters[player_id] += 1
    else:
        flag_counters[player_id] = 0  # reset on any clean window

    if flag_counters[player_id] >= FLAG_THRESHOLD:
        flag_counters[player_id] = 0
        return {
            "action": "block",
            "player_id": player_id,
            "human_score": result.human_score,
            "flags": result.flags,
        }

    return {"action": "allow", "human_score": result.human_score}


def post_match_analysis(session_id: str, session_trajectories: list[InputTrajectory]) -> dict:
    """Run after every match to catch mid-session aimbot activation."""
    analysis = analyze_session(session_id, session_trajectories)

    batch_result = batch_score(session_trajectories)
    adjusted = apply_calibration(batch_result, CALIBRATION)

    return {
        "session_id": session_id,
        "verdict": analysis.verdict,
        "risk_level": analysis.risk_level,
        "behavioral_shift_detected": analysis.behavioral_shift_detected,
        "shift_at_index": analysis.shift_at_index,
        "mean_human_score": adjusted.mean_human_score,
        "ban_recommended": (
            analysis.behavioral_shift_detected
            or analysis.verdict == "consistent_ai"
            or adjusted.mean_human_score < 0.35
        ),
    }
```

## Results

| Metric | Before | After |
|---|---|---|
| Bot detection rate | ~20 manual bans/week | 94% automated detection |
| False positive rate | 19% (accuracy-based) | 0.1% per trajectory |
| Detection latency | 8 hours (manual review) | <100ms (real-time) |
| Mid-session aimbot catches | Not possible | Detected via `behavioral_shift_detected` |
| Player churn citing "cheating" | 23% of exit surveys | 6% (3-month post-deploy) |
| Engineer hours on bot review | 40 hrs/week | 2 hrs/week (edge cases only) |

The 0.1% per-trajectory false positive rate combines with the three-consecutive-flag rule to
make wrongful bans operationally negligible. In the first 90 days after deployment, humanproof
processed 4.2 million trajectory windows across 50,000 daily players and issued zero confirmed
wrongful bans. Economy bots were cleared within the first two weeks as operators discovered
that injecting random noise into their macros — the obvious evasion — only made the trajectories
more human-like in `noise_ratio` and `correction_rate`, which is exactly the wrong direction
for a bot trying to stay undetected.

## Key Takeaways

- `analyze_session()` is the only reliable catch for players who activate aim assist mid-match;
  a session-averaged `MotorScore` masks the discrete transition entirely.
- The three-consecutive-flag rule (reset `flag_counters` on any clean window) drives the
  effective false positive rate from 0.1% to negligibly small without adding latency or
  infrastructure.
- `calibrate()` against a population-specific labeled set is not optional: the default thresholds
  are tuned for general web interactions, not competitive shooter inputs where even human
  `noise_ratio` clusters differently (pro players: 0.3-0.5; casual: 0.5-0.9).
- Sub-100ms detection latency means the enforcement layer can block an action *before* it
  executes — not after — which matters for one-shot abilities and economy transactions.
- Bots attempting to evade detection by injecting artificial noise inadvertently push their
  `noise_ratio` and `correction_rate` toward the human range, making evasion self-defeating.

## Try It Yourself

```bash
pip install humanproof

# Run the real-time detection simulation (5 players, 3 human / 2 bot)
python examples/realtime_game_integrity.py
```
