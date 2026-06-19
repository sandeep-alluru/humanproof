"""Anti-cheat detection for an online FPS match using humanproof motor-noise fingerprinting.

Story: Match #4521 — 10 players analyzed post-match. 7 humans, 3 AI bots.
The system flags bot players by their impossibly smooth, noise-free trajectories.

Run from repo root:
    python examples/game_anticheat.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from humanproof.scorer import MotorScorer
from humanproof.trajectory import InputSample, InputTrajectory

MATCH_ID = "4521"
RNG_SEED = 42


def make_human_trajectory(player_id: str, seed: int, num_samples: int = 200) -> InputTrajectory:
    """Generate a realistic human mouse trajectory: gaussian noise, micro-corrections, variable timing."""
    rng = random.Random(seed)
    samples: list[InputSample] = []

    # Human parameters: target direction with natural drift
    base_dx = rng.uniform(2.0, 6.0)
    base_dy = rng.uniform(1.5, 4.0)
    noise_std = rng.uniform(3.0, 5.5)  # pixel noise per step

    for i in range(num_samples):
        # Gaussian noise around base movement
        dx = rng.gauss(base_dx, noise_std)
        dy = rng.gauss(base_dy, noise_std)

        # Introduce micro-corrections (direction reversals) ~20% of the time
        if rng.random() < 0.20:
            dx = -dx * rng.uniform(0.3, 0.8)
            dy = -dy * rng.uniform(0.3, 0.8)

        # Human timing: variable 16-33ms between frames (monitor refresh jitter)
        dt = rng.uniform(16.0, 33.0)

        # Occasional speed bursts (flick shots, adrenaline)
        if rng.random() < 0.05:
            dx *= rng.uniform(2.5, 4.0)
            dy *= rng.uniform(2.5, 4.0)

        samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=float(i * 20)))

    return InputTrajectory(samples=samples, session_id=player_id)


def make_bot_trajectory(player_id: str, num_samples: int = 200) -> InputTrajectory:
    """Generate an AI bot trajectory: perfectly linear, constant 16ms, zero noise."""
    samples: list[InputSample] = []

    # Bot: perfectly constant movement vector — no noise, no corrections
    dx = 4.0
    dy = 3.0
    dt = 16.0  # locked to exactly one frame — superhuman consistency

    for i in range(num_samples):
        samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=float(i * dt)))

    return InputTrajectory(samples=samples, session_id=player_id)


def print_separator(char: str = "-", width: int = 72) -> None:
    print(char * width)


def main() -> None:
    random.seed(RNG_SEED)
    scorer = MotorScorer()

    # 10 players: 7 humans (001-007), 3 bots (008-010)
    players: list[tuple[str, InputTrajectory, str]] = []

    print(f"\n{'=' * 72}")
    print(f"  ANTI-CHEAT ENGINE v3.1  —  Match #{MATCH_ID}  —  Analyzing 10 players")
    print(f"{'=' * 72}\n")
    print("Collecting input samples... ", end="", flush=True)

    for i in range(1, 8):
        pid = f"player_{i:03d}"
        traj = make_human_trajectory(pid, seed=RNG_SEED + i)
        players.append((pid, traj, "human"))

    for i in range(8, 11):
        pid = f"player_{i:03d}"
        traj = make_bot_trajectory(pid)
        players.append((pid, traj, "bot"))

    print("done.\n")

    # Score all players
    results = []
    for pid, traj, true_label in players:
        score = scorer.score(traj)
        results.append((pid, score, true_label))

    # ── Print feature comparison table ────────────────────────────────────────
    print("FEATURE COMPARISON TABLE")
    print_separator()
    header = (
        f"{'Player':<14} {'noise_ratio':>12} {'correction_rt':>14} "
        f"{'smoothness':>12} {'human%':>8} {'verdict':>10}"
    )
    print(header)
    print_separator()

    flagged = []
    human_count = 0
    ai_count = 0

    for pid, score, true_label in results:
        f = score.features
        verdict_str = score.verdict.upper()
        marker = ""

        if score.verdict == "human":
            human_count += 1
        else:
            ai_count += 1
            flagged.append((pid, score))
            marker = "  <-- FLAGGED"

        print(
            f"{pid:<14} {f.noise_ratio:>12.4f} {f.correction_rate:>14.4f} "
            f"{f.smoothness:>12.2f} {score.human_score * 100:>7.1f}%"
            f" {verdict_str:>10}{marker}"
        )

    print_separator()

    # ── Match report ──────────────────────────────────────────────────────────
    print(f"\nANTI-CHEAT REPORT — Match #{MATCH_ID}:")
    print(f"  {human_count}/10 HUMAN    {ai_count}/10 AI")
    if flagged:
        flagged_names = ", ".join(pid for pid, _ in flagged)
        print(f"  Flagged for review: {flagged_names}")
    print()

    # ── Detailed flag breakdown ───────────────────────────────────────────────
    if flagged:
        print("FLAGGED PLAYER DETAILS")
        print_separator()
        for pid, score in flagged:
            conf_pct = score.ai_score * 100
            print(f"\n  {pid.upper()}")
            print(f"    Verdict:         AI  ({conf_pct:.0f}% confidence)")
            print(f"    noise_ratio:     {score.features.noise_ratio:.4f}  (human baseline: 0.40-0.80)")
            print(f"    correction_rate: {score.features.correction_rate:.4f}  (human baseline: 0.15-0.35)")
            print(f"    smoothness:      {score.features.smoothness:.2f}  (human baseline: <5.0)")
            print(f"    Anomaly flags:   {', '.join(score.flags) if score.flags else 'none'}")
            print(f"    Action:          ACCOUNT SUSPENDED — pending manual review")
        print()

    print_separator("=")
    print(f"  Match #{MATCH_ID} analysis complete.")
    print(f"  {human_count} players cleared  |  {ai_count} accounts flagged for suspension")
    print_separator("=")
    print()


if __name__ == "__main__":
    main()
