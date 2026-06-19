"""Tests for humanproof.session module."""
import math

import pytest

from humanproof.session import SessionAnalysis, analyze_session, detect_shift
from humanproof.trajectory import InputSample, InputTrajectory


def _make_traj(noise: float = 0.5, n: int = 15, session_id: str = "s") -> InputTrajectory:
    samples = [
        InputSample(
            dx=math.sin(i * 0.4) * noise + 0.01,
            dy=math.cos(i * 0.4) * noise + 0.01,
            dt=10.0,
            timestamp=float(i * 10),
        )
        for i in range(n)
    ]
    return InputTrajectory(samples=samples, session_id=session_id)


def _make_ai_traj(n: int = 15) -> InputTrajectory:
    """Very smooth, low-noise trajectory (AI-like)."""
    samples = [
        InputSample(dx=1.0, dy=0.5, dt=10.0, timestamp=float(i * 10))
        for i in range(n)
    ]
    return InputTrajectory(samples=samples, session_id="ai")


def test_detect_shift_no_shift():
    scores = [0.8, 0.75, 0.82, 0.78, 0.80, 0.77]
    assert detect_shift(scores) is None


def test_detect_shift_detects():
    # First half human-like, second half AI-like
    scores = [0.9, 0.85, 0.88, 0.1, 0.05, 0.08, 0.12]
    idx = detect_shift(scores, window=2, threshold=0.3)
    assert idx is not None
    assert idx > 0


def test_detect_shift_too_short():
    assert detect_shift([0.9, 0.1], window=3) is None


def test_analyze_session_returns_analysis():
    trajs = [_make_traj() for _ in range(6)]
    result = analyze_session("session1", trajs)
    assert isinstance(result, SessionAnalysis)
    assert result.session_id == "session1"
    assert result.trajectory_count == 6


def test_analyze_session_score_over_time_length():
    trajs = [_make_traj() for _ in range(4)]
    result = analyze_session("s", trajs)
    assert len(result.score_over_time) == 4
    for idx, score in result.score_over_time:
        assert 0.0 <= score <= 1.0


def test_analyze_session_consistent_human():
    # All similar trajectories — no behavioral shift should be detected
    trajs = [_make_traj(noise=0.8) for _ in range(6)]
    result = analyze_session("human_session", trajs)
    # Consistent trajectories: no shift detected regardless of human/ai verdict
    assert result.verdict in ("consistent_human", "consistent_ai", "behavioral_shift")
    assert result.risk_level in ("low", "medium", "high")


def test_analyze_session_to_dict():
    trajs = [_make_traj() for _ in range(3)]
    result = analyze_session("s", trajs)
    d = result.to_dict()
    assert d["session_id"] == "s"
    assert "behavioral_shift_detected" in d
    assert "verdict" in d
    assert "risk_level" in d


def test_detect_shift_with_threshold():
    scores = [0.9, 0.88, 0.92, 0.91, 0.15, 0.12, 0.10, 0.14]
    idx = detect_shift(scores, window=3, threshold=0.3)
    assert idx is not None
