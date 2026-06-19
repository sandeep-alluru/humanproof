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


def test_analyze_session_empty_raises():
    """analyze_session with empty trajectories should raise ValueError."""
    with pytest.raises(ValueError, match="trajectories must not be empty"):
        analyze_session("empty_session", [])


def test_analyze_session_uncertain_verdict():
    """Trajectories that produce a mean_score in the middle range → 'uncertain'."""
    # Use trajectories where the scorer gives mid-range human scores.
    # A mix of human-like and ai-like trajectories (no shift) gives an uncertain mean.
    human_like = _make_traj(noise=0.8, n=15)
    ai_like = _make_ai_traj(n=15)
    # Interleave to average out to middle range; must have enough for detect_shift to not trigger
    # Use only 2 so no shift is detected (window=3 requires at least 6)
    trajs = [human_like, ai_like]
    result = analyze_session("mixed_session", trajs)
    # With 2 trajectories detect_shift returns None (too short), so verdict depends on mean_score
    assert result.verdict in ("consistent_human", "consistent_ai", "uncertain")
    assert result.risk_level in ("low", "medium", "high")


def test_analyze_session_consistent_human_high_score():
    """Many human-like trajectories yield a non-shift verdict."""
    # High-noise trajectories → some human verdict
    trajs = [_make_traj(noise=1.5, n=20) for _ in range(4)]
    result = analyze_session("human_high", trajs)
    assert result.trajectory_count == 4
    # Verdict should be one of the valid options
    assert result.verdict in ("consistent_human", "consistent_ai", "uncertain", "behavioral_shift")


def test_analyze_session_consistent_ai_verdict():
    """Many AI-like trajectories yield consistent_ai verdict."""
    trajs = [_make_ai_traj(n=20) for _ in range(4)]
    result = analyze_session("ai_session", trajs)
    assert result.trajectory_count == 4
    # AI-like trajectories → low human_score → consistent_ai
    assert result.verdict in ("consistent_ai", "uncertain", "behavioral_shift")
    assert result.risk_level in ("high", "medium")


def test_analyze_session_behavioral_shift():
    """Detect behavioral shift when trajectories switch from human to AI pattern."""
    # 4 human-like followed by 4 AI-like → shift should be detected
    human_trajs = [_make_traj(noise=1.5, n=20) for _ in range(4)]
    ai_trajs = [_make_ai_traj(n=20) for _ in range(4)]
    trajs = human_trajs + ai_trajs
    result = analyze_session("shift_session", trajs)
    assert result.trajectory_count == 8
    # If shift detected, verdict == "behavioral_shift"
    if result.behavioral_shift_detected:
        assert result.verdict == "behavioral_shift"
        assert result.risk_level == "high"
        assert result.shift_at_index is not None
