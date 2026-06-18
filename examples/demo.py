"""Demo script showing humanproof motor-noise fingerprinting."""

from __future__ import annotations

import random
import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from humanproof.trajectory import InputSample, InputTrajectory
from humanproof.scorer import MotorScorer
from humanproof.report import print_score, to_json


def make_ai_trajectory() -> InputTrajectory:
    """Simulate an AI agent: perfectly smooth, zero noise."""
    samples = [InputSample(dx=5.0, dy=5.0, dt=10.0) for _ in range(30)]
    return InputTrajectory(samples=samples, session_id="ai_demo")


def make_human_trajectory() -> InputTrajectory:
    """Simulate a human: noisy with direction corrections."""
    random.seed(123)
    samples = []
    for i in range(30):
        dx = random.gauss(4.0, 2.5)
        dy = random.gauss(3.0, 2.0)
        dt = random.uniform(8.0, 14.0)
        samples.append(InputSample(dx=dx, dy=dy, dt=dt))
    # Add some corrections
    for idx in [7, 14, 22]:
        samples[idx] = InputSample(
            dx=-abs(samples[idx].dx),
            dy=-abs(samples[idx].dy),
            dt=10.0,
        )
    return InputTrajectory(samples=samples, session_id="human_demo")


def main() -> None:
    scorer = MotorScorer()

    print("\n=== humanproof Motor-Noise Fingerprinting Demo ===\n")

    # Score AI trajectory
    ai_traj = make_ai_trajectory()
    ai_result = scorer.score(ai_traj)
    print("AI-like trajectory:")
    print_score(ai_result)

    print()

    # Score human trajectory
    human_traj = make_human_trajectory()
    human_result = scorer.score(human_traj)
    print("Human-like trajectory:")
    print_score(human_result)

    print()

    # Batch scoring
    all_results = scorer.batch_score([ai_traj, human_traj])
    print(f"\nBatch scored {len(all_results)} trajectories.")
    print("\nJSON output (first result):")
    print(to_json([all_results[0]]))


if __name__ == "__main__":
    main()
