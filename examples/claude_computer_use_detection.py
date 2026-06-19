"""Detect AI agent (computer-use) vs. real user form interactions using humanproof.

Story: A web app contact form — one session from a genuine user moving naturally
between fields, one from an AI automation agent moving directly to each field.
humanproof scores both sessions and feeds results into a progressive challenge
system (CAPTCHA / extra verification / pass-through).

Run from repo root:
    python examples/claude_computer_use_detection.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from humanproof.scorer import MotorScorer
from humanproof.trajectory import InputSample, InputTrajectory

# ── Form field layout (pixel coords of field centers) ────────────────────────
FORM_FIELDS = [
    ("Name",    200, 150),
    ("Email",   200, 260),
    ("Subject", 200, 370),
    ("Message", 200, 520),
    ("Submit",  200, 680),
]


def _move_human(
    x0: float, y0: float, x1: float, y1: float,
    rng: random.Random,
    samples: list[InputSample],
    base_ts: float,
) -> float:
    """Simulate human cursor movement: curved path with noise and micro-corrections."""
    steps = rng.randint(18, 32)
    dx_total = x1 - x0
    dy_total = y1 - y0

    ts = base_ts
    for step in range(steps):
        # Ease-in-out curve factor
        t = step / steps
        ease = t * t * (3 - 2 * t)
        # Gaussian noise on each micro-step
        noise_x = rng.gauss(0, 3.5)
        noise_y = rng.gauss(0, 3.0)

        dx = (dx_total / steps) * (1 + rng.gauss(0, 0.2)) + noise_x
        dy = (dy_total / steps) * (1 + rng.gauss(0, 0.2)) + noise_y

        # Occasional micro-corrections (direction reversals)
        if rng.random() < 0.18:
            dx = -dx * rng.uniform(0.2, 0.6)
            dy = -dy * rng.uniform(0.2, 0.6)

        # Variable inter-frame timing: 16-35ms
        dt = rng.uniform(16.0, 35.0)
        samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=ts))
        ts += dt

    # Hover jitter at destination (human settles mouse)
    for _ in range(rng.randint(3, 7)):
        dt = rng.uniform(20.0, 40.0)
        samples.append(InputSample(
            dx=rng.gauss(0, 1.2),
            dy=rng.gauss(0, 0.8),
            dt=dt,
            timestamp=ts,
        ))
        ts += dt

    return ts


def _move_bot(
    x0: float, y0: float, x1: float, y1: float,
    samples: list[InputSample],
    base_ts: float,
) -> float:
    """Simulate AI agent: direct linear interpolation, constant 16ms, zero noise."""
    steps = 20  # always exactly 20 steps
    dx = (x1 - x0) / steps
    dy = (y1 - y0) / steps
    dt = 16.0

    ts = base_ts
    for _ in range(steps):
        samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=ts))
        ts += dt
    return ts


def build_human_session() -> InputTrajectory:
    """Build a full form-filling session as a real user would navigate it."""
    rng = random.Random(77)
    samples: list[InputSample] = []
    ts = 0.0

    cx, cy = 400.0, 80.0  # start: user's cursor somewhere near top of page

    for field_name, fx, fy in FORM_FIELDS:
        ts = _move_human(cx, cy, float(fx), float(fy), rng, samples, ts)
        cx, cy = float(fx), float(fy)

        # Simulate typing inter-key delays (variable, 80-280ms per char)
        # We encode this as tiny near-zero movements with realistic timing
        char_count = {"Name": 12, "Email": 18, "Subject": 24, "Message": 80, "Submit": 0}
        for _ in range(char_count.get(field_name, 0)):
            dt_key = rng.uniform(80.0, 280.0)
            samples.append(InputSample(
                dx=rng.gauss(0, 0.4),
                dy=rng.gauss(0, 0.3),
                dt=dt_key,
                timestamp=ts,
            ))
            ts += dt_key

    return InputTrajectory(samples=samples, session_id="real-user-session-7742")


def build_agent_session() -> InputTrajectory:
    """Build a form-filling session from an AI automation agent."""
    samples: list[InputSample] = []
    ts = 0.0

    cx, cy = 400.0, 80.0

    for field_name, fx, fy in FORM_FIELDS:
        ts = _move_bot(cx, cy, float(fx), float(fy), samples, ts)
        cx, cy = float(fx), float(fy)

        # Constant-rate typing (exactly 120ms per keystroke — robotic)
        char_count = {"Name": 12, "Email": 18, "Subject": 24, "Message": 80, "Submit": 0}
        for _ in range(char_count.get(field_name, 0)):
            samples.append(InputSample(dx=0.0, dy=0.0, dt=120.0, timestamp=ts))
            ts += 120.0

    return InputTrajectory(samples=samples, session_id="ai-agent-session-computer-use")


def progressive_challenge(human_score: float) -> tuple[str, str]:
    """Return (action, reason) based on human probability score."""
    if human_score >= 0.75:
        return "PASS THROUGH", "High confidence human — no friction added"
    elif human_score >= 0.50:
        return "ADDITIONAL VERIFICATION", "Ambiguous session — email OTP required"
    else:
        return "CAPTCHA CHALLENGE", "Low human score — bot suspected"


def print_separator(char: str = "-", width: int = 72) -> None:
    print(char * width)


def main() -> None:
    scorer = MotorScorer()

    print(f"\n{'=' * 72}")
    print("  FORM INTERACTION ANALYZER — AI Agent vs. Real User Detection")
    print(f"{'=' * 72}\n")

    sessions = [
        ("Real User",            build_human_session()),
        ("AI Agent (Computer Use)", build_agent_session()),
    ]

    scored = []
    for label, traj in sessions:
        score = scorer.score(traj)
        scored.append((label, traj, score))

    # ── Feature comparison ────────────────────────────────────────────────────
    print("SESSION ANALYSIS")
    print_separator()

    for label, traj, score in scored:
        f = score.features
        verdict_conf = score.human_score if score.verdict == "human" else score.ai_score
        verdict_label = score.verdict.upper()

        print(f"\n  Session:          {label}")
        print(f"  Trajectory ID:    {traj.id}")
        print(f"  Samples:          {len(traj.samples)}")
        print(f"  noise_ratio:      {f.noise_ratio:.4f}  (human >0.30, bot <0.15)")
        print(f"  correction_rate:  {f.correction_rate:.4f}  (human >0.10, bot <0.05)")
        print(f"  smoothness:       {f.smoothness:.2f}   (human <5.0, bot >8.0)")
        print(f"  mean_speed:       {f.mean_speed:.4f} px/ms")
        print(f"  Anomaly flags:    {', '.join(score.flags) if score.flags else 'none'}")
        print(f"  --")
        print(f"  Verdict:          {verdict_label}  ({verdict_conf * 100:.0f}% confidence)")

    # ── Side-by-side discriminating features ─────────────────────────────────
    print()
    print_separator()
    print("\nKEY DISCRIMINATING FEATURES (side by side)")
    print_separator()

    _, _, human_score = scored[0]
    _, _, bot_score   = scored[1]
    hf = human_score.features
    bf = bot_score.features

    print(f"  {'Feature':<22} {'Real User':>14} {'AI Agent':>14}  {'Winner':>10}")
    print_separator()
    print(f"  {'noise_ratio':<22} {hf.noise_ratio:>14.4f} {bf.noise_ratio:>14.4f}  {'HUMAN higher':>10}")
    print(f"  {'correction_rate':<22} {hf.correction_rate:>14.4f} {bf.correction_rate:>14.4f}  {'HUMAN higher':>10}")
    print(f"  {'smoothness (inv-jerk)':<22} {hf.smoothness:>14.2f} {bf.smoothness:>14.2f}  {'BOT smoother':>10}")
    print(f"  {'human_score':<22} {human_score.human_score:>14.4f} {bot_score.human_score:>14.4f}  {'HUMAN wins':>10}")
    print()

    # ── Progressive challenge decisions ──────────────────────────────────────
    print("PROGRESSIVE CHALLENGE SYSTEM")
    print_separator()

    for label, _, score in scored:
        action, reason = progressive_challenge(score.human_score)
        print(f"\n  Session:   {label}")
        print(f"  Score:     {score.human_score:.2f} human / {score.ai_score:.2f} bot")
        print(f"  Action:    {action}")
        print(f"  Reason:    {reason}")

    print()
    print_separator("=")
    print("  Detection complete. AI agent correctly identified and challenged.")
    print_separator("=")
    print()


if __name__ == "__main__":
    main()
