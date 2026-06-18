"""humanproof — Motor-noise fingerprinting for AI detection in competitive games."""

from __future__ import annotations

from importlib.metadata import version as _version

from humanproof.trajectory import InputSample, InputTrajectory
from humanproof.scorer import MotorFeatures, MotorScore, MotorScorer

__version__ = _version("humanproof")

__all__ = [
    "InputSample",
    "InputTrajectory",
    "MotorFeatures",
    "MotorScore",
    "MotorScorer",
]
