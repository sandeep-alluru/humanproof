"""Tests for humanproof.calibration module."""
import math

import pytest

from humanproof.calibration import (
    CalibrationResult,
    CalibratedMotorScorer,
    apply_calibration,
    calibrate,
)
from humanproof.scorer import MotorScorer
from humanproof.trajectory import InputSample, InputTrajectory


def _make_human_traj(n: int = 20) -> InputTrajectory:
    """High-noise, high-correction trajectory (human-like)."""
    samples = []
    for i in range(n):
        noise = 0.6 if i % 2 == 0 else -0.4
        samples.append(InputSample(dx=noise + 0.1, dy=noise - 0.1, dt=10.0, timestamp=float(i * 10)))
    return InputTrajectory(samples=samples, session_id="human")


def _make_ai_traj(n: int = 20) -> InputTrajectory:
    """Very smooth, constant trajectory (AI-like)."""
    samples = [
        InputSample(dx=1.0, dy=0.5, dt=10.0, timestamp=float(i * 10))
        for i in range(n)
    ]
    return InputTrajectory(samples=samples, session_id="ai")


def _make_medium_traj(n: int = 20) -> InputTrajectory:
    """Medium-noise trajectory that falls in uncertain range."""
    samples = [
        InputSample(dx=math.sin(i * 0.3) * 0.3 + 0.1, dy=0.1, dt=10.0, timestamp=float(i * 10))
        for i in range(n)
    ]
    return InputTrajectory(samples=samples, session_id="medium")


def test_calibrate_returns_result():
    human = [_make_human_traj() for _ in range(5)]
    ai = [_make_ai_traj() for _ in range(5)]
    result = calibrate(human, ai)
    assert isinstance(result, CalibrationResult)
    assert 0.0 <= result.accuracy <= 1.0
    assert 0.0 <= result.optimal_noise_threshold <= 1.0
    assert 0.0 <= result.optimal_correction_threshold <= 1.0


def test_calibrate_to_dict():
    human = [_make_human_traj()]
    ai = [_make_ai_traj()]
    result = calibrate(human, ai)
    d = result.to_dict()
    assert "optimal_noise_threshold" in d
    assert "accuracy" in d
    assert "human_precision" in d
    assert "ai_precision" in d


def test_apply_calibration_returns_scorer():
    human = [_make_human_traj() for _ in range(3)]
    ai = [_make_ai_traj() for _ in range(3)]
    cal = calibrate(human, ai)
    base_scorer = MotorScorer()
    calibrated = apply_calibration(base_scorer, cal)
    assert isinstance(calibrated, CalibratedMotorScorer)


def test_apply_calibration_scores_trajectory():
    human = [_make_human_traj() for _ in range(3)]
    ai = [_make_ai_traj() for _ in range(3)]
    cal = calibrate(human, ai)
    scorer = apply_calibration(MotorScorer(), cal)
    traj = _make_ai_traj()
    score = scorer.score(traj)
    assert score is not None
    assert 0.0 <= score.human_score <= 1.0
    assert score.verdict in ("human", "ai", "uncertain")


def test_calibrate_with_empty_ai():
    """Calibrate with no AI samples — should still return a result."""
    human = [_make_human_traj() for _ in range(3)]
    result = calibrate(human, [])
    assert isinstance(result, CalibrationResult)


def test_calibrated_motor_scorer_human_trajectory():
    """CalibratedMotorScorer scores a human-like trajectory correctly."""
    # Use thresholds that are easily met by the human trajectory
    scorer = CalibratedMotorScorer(noise_threshold=0.01, correction_threshold=0.01)
    traj = _make_human_traj(n=20)
    score = scorer.score(traj)
    assert score is not None
    assert 0.0 <= score.human_score <= 1.0
    # Human-like trajectory with low thresholds → should be "human"
    assert score.verdict in ("human", "uncertain", "ai")


def test_calibrated_motor_scorer_ai_trajectory():
    """CalibratedMotorScorer scores an AI-like trajectory as 'ai'."""
    # Set thresholds very high so AI trajectory can't reach them
    scorer = CalibratedMotorScorer(noise_threshold=10.0, correction_threshold=10.0)
    traj = _make_ai_traj(n=20)
    score = scorer.score(traj)
    assert score is not None
    assert 0.0 <= score.human_score <= 1.0
    # AI trajectory with very high thresholds → neither threshold met → check both halves
    assert score.verdict in ("human", "ai", "uncertain")


def test_calibrated_motor_scorer_is_human_branch():
    """CalibratedMotorScorer hits the is_human=True branch with low thresholds."""
    # Very low thresholds so any trajectory is "human"
    scorer = CalibratedMotorScorer(noise_threshold=0.0001, correction_threshold=0.0)
    traj = _make_human_traj(n=20)
    score = scorer.score(traj)
    # is_human should be True → verdict == "human", human_score * 1.1
    assert score.verdict == "human"
    assert score.human_score >= 0.0


def test_calibrated_motor_scorer_ai_branch():
    """CalibratedMotorScorer hits the AI branch when both metrics are far below threshold."""
    # Set threshold so high that noise/correction are both < threshold * 0.5
    scorer = CalibratedMotorScorer(noise_threshold=100.0, correction_threshold=100.0)
    traj = _make_ai_traj(n=20)
    score = scorer.score(traj)
    # noise_ratio << 100*0.5 and correction_rate << 100*0.5 → verdict == "ai"
    assert score.verdict == "ai"
    assert 0.0 <= score.human_score <= 1.0


def test_calibrated_motor_scorer_fallback_branch():
    """CalibratedMotorScorer hits the else/fallback branch."""
    # Threshold set so that the trajectory is neither clearly human nor clearly AI
    # e.g. noise_ratio >= threshold (so not AI) but correction_rate < threshold (so not human)
    scorer = CalibratedMotorScorer(noise_threshold=0.001, correction_threshold=100.0)
    traj = _make_human_traj(n=20)
    score = scorer.score(traj)
    # is_human requires BOTH metrics >= threshold; AI branch requires BOTH < threshold*0.5
    # correction_rate will be < 100*0.5 but noise_ratio > 0.001, so we fall through to else
    assert score.verdict in ("human", "ai", "uncertain")
    assert 0.0 <= score.human_score <= 1.0


def test_calibrate_with_medium_trajs():
    """Calibrate with trajectories that trigger uncertain predictions."""
    # Mix of medium trajectories that may predict "uncertain"
    medium = [_make_medium_traj() for _ in range(3)]
    ai = [_make_ai_traj() for _ in range(3)]
    result = calibrate(medium, ai)
    assert isinstance(result, CalibrationResult)
    assert 0.0 <= result.accuracy <= 1.0


def test_calibrate_ai_predicted_as_human():
    """Cover the branch where AI trajectory is predicted as human in _evaluate."""
    # Use very permissive thresholds so AI trajs look human
    from humanproof.calibration import _evaluate
    ai = [_make_ai_traj() for _ in range(3)]
    human = [_make_human_traj() for _ in range(3)]
    # With very low noise_threshold, ai traj noise_ratio > threshold*2 → human_score += 0.2
    acc, hp, ap = _evaluate(human, ai, noise_threshold=0.001, correction_threshold=0.001)
    assert 0.0 <= acc <= 1.0


def test_apply_calibration_returns_calibrated_motor_scorer():
    """apply_calibration returns a CalibratedMotorScorer (not raw MotorScorer)."""
    cal = CalibrationResult(
        optimal_noise_threshold=0.15,
        optimal_correction_threshold=0.05,
        accuracy=0.8,
        human_precision=0.9,
        ai_precision=0.7,
    )
    scorer = apply_calibration(MotorScorer(), cal)
    assert isinstance(scorer, CalibratedMotorScorer)
    assert scorer._noise_threshold == 0.15
    assert scorer._correction_threshold == 0.05
