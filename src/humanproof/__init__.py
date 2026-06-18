"""humanproof — Motor-noise fingerprinting for AI detection in competitive games."""

from __future__ import annotations

from importlib.metadata import version as _version

from humanproof.scorer import MotorFeatures, MotorScore, MotorScorer
from humanproof.trajectory import InputSample, InputTrajectory

__version__ = _version("humanproof")

__all__ = [
    "InputSample",
    "InputTrajectory",
    "MotorFeatures",
    "MotorScore",
    "MotorScorer",
]
