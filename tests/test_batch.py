"""Tests for humanproof.batch module."""
import csv
import tempfile
from pathlib import Path

import pytest

from humanproof.batch import BatchScoreResult, batch_score, score_from_csv
from humanproof.trajectory import InputSample, InputTrajectory


def _make_traj(noise_level: float = 0.5, n: int = 20) -> InputTrajectory:
    """Create a trajectory with controlled noise."""
    import math
    samples = []
    for i in range(n):
        dx = math.sin(i * 0.3) * noise_level + (0.1 if i % 3 == 0 else 0)
        dy = math.cos(i * 0.3) * noise_level
        samples.append(InputSample(dx=dx + 0.01, dy=dy + 0.01, dt=10.0, timestamp=float(i * 10)))
    return InputTrajectory(samples=samples, session_id="test")


def test_batch_score_returns_result():
    trajs = [_make_traj() for _ in range(5)]
    result = batch_score(trajs)
    assert isinstance(result, BatchScoreResult)
    assert len(result.scores) == 5
    assert result.human_count + result.ai_count + result.uncertain_count == 5


def test_batch_score_empty():
    result = batch_score([])
    assert result.human_count == 0
    assert result.ai_count == 0
    assert result.mean_human_score == 0.0


def test_batch_score_summary_string():
    trajs = [_make_traj() for _ in range(3)]
    result = batch_score(trajs)
    assert "Scored 3 trajectories" in result.summary


def test_batch_score_flagged():
    trajs = [_make_traj() for _ in range(3)]
    result = batch_score(trajs)
    for fid in result.flagged_trajectories:
        assert any(s.trajectory_id == fid and s.verdict == "ai" for s in result.scores)


def test_to_dict():
    trajs = [_make_traj()]
    result = batch_score(trajs)
    d = result.to_dict()
    assert "human_count" in d
    assert "scores" in d
    assert isinstance(d["scores"], list)


def test_score_from_csv(tmp_path: Path):
    csv_file = tmp_path / "test.csv"
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["trajectory_id", "t", "x", "y", "button"])
        writer.writeheader()
        # Two trajectories with 5 points each
        for i in range(5):
            writer.writerow({"trajectory_id": "traj1", "t": i * 10, "x": i * 2.0, "y": i * 1.5, "button": 0})
        for i in range(5):
            writer.writerow({"trajectory_id": "traj2", "t": i * 10, "x": i * 0.1, "y": i * 0.05, "button": 0})
    result = score_from_csv(csv_file)
    assert isinstance(result, BatchScoreResult)
    assert len(result.scores) == 2


def test_score_from_csv_single_row_trajectory(tmp_path: Path):
    """A trajectory with only 1 row produces 0 samples — should be skipped gracefully."""
    csv_file = tmp_path / "single.csv"
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["trajectory_id", "t", "x", "y", "button"])
        writer.writeheader()
        writer.writerow({"trajectory_id": "only_one", "t": 0, "x": 1, "y": 1, "button": 0})
        for i in range(5):
            writer.writerow({"trajectory_id": "good", "t": i * 10, "x": i * 3.0, "y": i * 2.0, "button": 0})
    result = score_from_csv(csv_file)
    # only 'good' trajectory should be scored
    assert len(result.scores) == 1


def test_score_from_csv_zero_dt_fallback(tmp_path: Path):
    """When two rows have the same timestamp, dt would be 0; should fall back to dt=1.0."""
    csv_file = tmp_path / "zerodt.csv"
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["trajectory_id", "t", "x", "y", "button"])
        writer.writeheader()
        # Same timestamp for two rows → dt = 0 → should be clamped to 1.0
        writer.writerow({"trajectory_id": "dup_t", "t": 0, "x": 0.0, "y": 0.0, "button": 0})
        writer.writerow({"trajectory_id": "dup_t", "t": 0, "x": 1.0, "y": 1.0, "button": 0})
        # Also add a normal row so the trajectory is valid
        writer.writerow({"trajectory_id": "dup_t", "t": 10, "x": 2.0, "y": 2.0, "button": 0})
    result = score_from_csv(csv_file)
    assert isinstance(result, BatchScoreResult)
    assert len(result.scores) == 1
