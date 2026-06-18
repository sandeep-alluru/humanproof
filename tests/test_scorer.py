"""Tests for MotorScorer, MotorFeatures, and MotorScore."""

from __future__ import annotations

from humanproof.scorer import MotorFeatures, MotorScore, MotorScorer
from humanproof.trajectory import InputSample, InputTrajectory


def make_ai_traj() -> InputTrajectory:
    """Smooth, low-noise trajectory (AI-like)."""
    samples = [InputSample(dx=5.0, dy=5.0, dt=10.0) for _ in range(20)]
    return InputTrajectory(samples=samples, session_id="ai_test")


def make_human_traj() -> InputTrajectory:
    """Noisy trajectory with corrections (human-like)."""
    import random
    random.seed(42)
    samples = []
    for _i in range(20):
        dx = random.gauss(3.0, 2.0)
        dy = random.gauss(3.0, 2.0)
        dt = 10.0
        samples.append(InputSample(dx=dx, dy=dy, dt=dt))
    samples[5] = InputSample(dx=-5.0, dy=-3.0, dt=10.0)
    samples[10] = InputSample(dx=-4.0, dy=2.0, dt=10.0)
    samples[15] = InputSample(dx=-3.0, dy=-5.0, dt=10.0)
    return InputTrajectory(samples=samples, session_id="human_test")


scorer = MotorScorer()


# MotorFeatures tests
def test_extract_features_returns_motor_features() -> None:
    traj = make_ai_traj()
    features = scorer.extract_features(traj)
    assert isinstance(features, MotorFeatures)


def test_extract_features_mean_speed_positive() -> None:
    samples = [InputSample(dx=3.0, dy=4.0, dt=10.0) for _ in range(5)]
    traj = InputTrajectory(samples=samples)
    features = scorer.extract_features(traj)
    assert features.mean_speed > 0


def test_extract_features_smoothness_high_for_uniform() -> None:
    samples = [InputSample(dx=3.0, dy=4.0, dt=10.0) for _ in range(10)]
    traj = InputTrajectory(samples=samples)
    features = scorer.extract_features(traj)
    assert features.smoothness > 100


def test_extract_features_noise_ratio_zero_for_uniform() -> None:
    samples = [InputSample(dx=3.0, dy=4.0, dt=10.0) for _ in range(5)]
    traj = InputTrajectory(samples=samples)
    features = scorer.extract_features(traj)
    assert features.noise_ratio == 0.0


def test_extract_features_correction_rate() -> None:
    samples = [
        InputSample(dx=1.0, dy=1.0, dt=10.0),
        InputSample(dx=-1.0, dy=1.0, dt=10.0),
        InputSample(dx=1.0, dy=1.0, dt=10.0),
    ]
    traj = InputTrajectory(samples=samples)
    features = scorer.extract_features(traj)
    assert features.correction_rate > 0


def test_extract_features_to_dict() -> None:
    traj = make_ai_traj()
    features = scorer.extract_features(traj)
    d = features.to_dict()
    assert "mean_speed" in d
    assert "noise_ratio" in d
    assert "correction_rate" in d
    assert "smoothness" in d


# MotorScorer.score tests
def test_score_returns_motor_score() -> None:
    traj = make_ai_traj()
    result = scorer.score(traj)
    assert isinstance(result, MotorScore)


def test_score_trajectory_id_matches() -> None:
    traj = make_ai_traj()
    result = scorer.score(traj)
    assert result.trajectory_id == traj.id


def test_score_human_plus_ai_equals_one() -> None:
    traj = make_ai_traj()
    result = scorer.score(traj)
    assert abs(result.human_score + result.ai_score - 1.0) < 1e-9


def test_score_verdict_valid_values() -> None:
    traj = make_ai_traj()
    result = scorer.score(traj)
    assert result.verdict in ("human", "ai", "uncertain")


def test_score_ai_input_low_human_score() -> None:
    """Smooth, uniform AI input should score low human_score."""
    traj = make_ai_traj()
    result = scorer.score(traj)
    assert result.human_score < 0.5


def test_score_ai_input_verdict_ai() -> None:
    traj = make_ai_traj()
    result = scorer.score(traj)
    assert result.verdict in ("ai", "uncertain")


def test_score_human_input_higher_score() -> None:
    """Noisy human-like input should score higher human_score."""
    human_traj = make_human_traj()
    ai_traj = make_ai_traj()
    human_result = scorer.score(human_traj)
    ai_result = scorer.score(ai_traj)
    assert human_result.human_score > ai_result.human_score


def test_score_flags_for_ai() -> None:
    """AI-like trajectory should trigger at least one flag."""
    traj = make_ai_traj()
    result = scorer.score(traj)
    assert len(result.flags) > 0


def test_score_human_score_clamped() -> None:
    traj = make_ai_traj()
    result = scorer.score(traj)
    assert 0.0 <= result.human_score <= 1.0
    assert 0.0 <= result.ai_score <= 1.0


def test_score_to_dict_keys() -> None:
    traj = make_ai_traj()
    result = scorer.score(traj)
    d = result.to_dict()
    assert "trajectory_id" in d
    assert "human_score" in d
    assert "ai_score" in d
    assert "verdict" in d
    assert "flags" in d
    assert "features" in d


def test_batch_score_returns_list() -> None:
    trajs = [make_ai_traj(), make_human_traj()]
    results = scorer.batch_score(trajs)
    assert len(results) == 2


def test_batch_score_empty() -> None:
    results = scorer.batch_score([])
    assert results == []


def test_score_verdict_human_for_high_score() -> None:
    """Manually construct a high human_score scenario."""
    samples = []
    for i in range(20):
        sign = 1 if i % 2 == 0 else -1
        samples.append(InputSample(dx=sign * float(i + 1) * 2, dy=float(i + 1), dt=10.0))
    traj = InputTrajectory(samples=samples)
    result = scorer.score(traj)
    assert result.verdict in ("human", "uncertain")
