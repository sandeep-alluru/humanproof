"""humanproof — Motor-noise fingerprinting + HITL approval gates for agents."""

from __future__ import annotations

from importlib.metadata import version as _version

from humanproof.batch import BatchScoreResult, batch_score, score_from_csv
from humanproof.calibration import (
    CalibratedMotorScorer,
    CalibrationResult,
    apply_calibration,
    calibrate,
)
from humanproof.closed_loop import (
    ApprovalError,
    ApprovalSession,
    ApprovalToken,
    GateOutcome,
    assert_approved,
    gate_approval,
    require_token_for,
)
from humanproof.scorer import MotorFeatures, MotorScore, MotorScorer
from humanproof.session import SessionAnalysis, analyze_session, detect_shift
from humanproof.trajectory import InputSample, InputTrajectory

__version__ = _version("humanproof")

__all__ = [
    "ApprovalError",
    "ApprovalSession",
    "ApprovalToken",
    "BatchScoreResult",
    "CalibratedMotorScorer",
    "CalibrationResult",
    "GateOutcome",
    "InputSample",
    "InputTrajectory",
    "MotorFeatures",
    "MotorScore",
    "MotorScorer",
    "SessionAnalysis",
    "analyze_session",
    "apply_calibration",
    "assert_approved",
    "batch_score",
    "calibrate",
    "detect_shift",
    "gate_approval",
    "require_token_for",
    "score_from_csv",
]
