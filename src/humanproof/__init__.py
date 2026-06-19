"""humanproof — Motor-noise fingerprinting for AI detection in competitive games."""

from __future__ import annotations

from importlib.metadata import version as _version

from humanproof.batch import BatchScoreResult, batch_score, score_from_csv
from humanproof.calibration import CalibrationResult, apply_calibration, calibrate
from humanproof.scorer import MotorFeatures, MotorScore, MotorScorer
from humanproof.session import SessionAnalysis, analyze_session, detect_shift
from humanproof.trajectory import InputSample, InputTrajectory

__version__ = _version("humanproof")

__all__ = [
    "BatchScoreResult",
    "CalibrationResult",
    "InputSample",
    "InputTrajectory",
    "MotorFeatures",
    "MotorScore",
    "MotorScorer",
    "SessionAnalysis",
    "analyze_session",
    "apply_calibration",
    "batch_score",
    "calibrate",
    "detect_shift",
    "score_from_csv",
]
