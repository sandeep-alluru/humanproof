"""Tests for humanproof.calibration module."""
import math

import pytest

from humanproof.calibration import CalibrationResult, apply_calibration, calibrate
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
    assert isinstance(calibrated, MotorScorer)


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
