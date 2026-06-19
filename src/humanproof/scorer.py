"""Motor feature extraction and scoring."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from humanproof.trajectory import InputTrajectory


@dataclass
class MotorFeatures:
    """Statistical features extracted from an input trajectory.

    Attributes:
        mean_speed: Mean speed in pixels/ms.
        speed_std: Standard deviation of speed.
        noise_ratio: std/mean speed. Humans ~0.4-0.8, AIs ~0.05-0.2.
        correction_rate: Corrections per sample. Humans ~0.15-0.35.
        jerk_mean: Mean absolute jerk.
        jerk_std: Standard deviation of jerk.
        max_speed: Maximum speed.
        smoothness: Inverse of mean jerk (higher = smoother, more AI-like).
    """

    mean_speed: float
    speed_std: float
    noise_ratio: float
    correction_rate: float
    jerk_mean: float
    jerk_std: float
    max_speed: float
    smoothness: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "mean_speed": self.mean_speed,
            "speed_std": self.speed_std,
            "noise_ratio": self.noise_ratio,
            "correction_rate": self.correction_rate,
            "jerk_mean": self.jerk_mean,
            "jerk_std": self.jerk_std,
            "max_speed": self.max_speed,
            "smoothness": self.smoothness,
        }


@dataclass
class MotorScore:
    """The scored result for a single trajectory.

    Attributes:
        trajectory_id: ID of the scored trajectory.
        features: Extracted motor features.
        human_score: Probability of human input [0.0, 1.0].
        ai_score: Probability of AI input (1.0 - human_score).
        verdict: "human", "ai", or "uncertain".
        flags: List of flagged anomalies.
    """

    trajectory_id: str
    features: MotorFeatures
    human_score: float
    ai_score: float
    verdict: str
    flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "trajectory_id": self.trajectory_id,
            "features": self.features.to_dict(),
            "human_score": self.human_score,
            "ai_score": self.ai_score,
            "verdict": self.verdict,
            "flags": self.flags,
        }


class MotorScorer:
    """Score trajectories using threshold-based heuristics on motor features.

    Human ranges: noise_ratio > 0.3, correction_rate > 0.1, smoothness < 5.0
    AI ranges:    noise_ratio < 0.15, correction_rate < 0.05, smoothness > 8.0
    """

    def extract_features(self, traj: InputTrajectory) -> MotorFeatures:
        """Extract MotorFeatures from a trajectory."""
        vp = traj.velocity_profile()
        jp = traj.jerk_profile()
        n = len(traj.samples)

        mean_speed = sum(vp) / len(vp) if vp else 0.0
        speed_variance = sum((v - mean_speed) ** 2 for v in vp) / len(vp) if vp else 0.0
        speed_std = math.sqrt(speed_variance)
        max_speed = max(vp) if vp else 0.0
        noise_ratio = traj.noise_ratio()
        correction_rate = traj.correction_count() / n if n > 0 else 0.0

        abs_jerks = [abs(j) for j in jp]
        jerk_mean = sum(abs_jerks) / len(abs_jerks) if abs_jerks else 0.0
        jerk_variance = (
            sum((j - jerk_mean) ** 2 for j in abs_jerks) / len(abs_jerks)
            if abs_jerks else 0.0
        )
        jerk_std = math.sqrt(jerk_variance)
        smoothness = 1.0 / (jerk_mean + 1e-9)

        return MotorFeatures(
            mean_speed=mean_speed,
            speed_std=speed_std,
            noise_ratio=noise_ratio,
            correction_rate=correction_rate,
            jerk_mean=jerk_mean,
            jerk_std=jerk_std,
            max_speed=max_speed,
            smoothness=smoothness,
        )

    def score(self, traj: InputTrajectory) -> MotorScore:
        """Score a trajectory and return a MotorScore."""
        features = self.extract_features(traj)
        flags: list[str] = []
        human_score = 0.5

        # noise_ratio: < 0.15 → AI, > 0.3 → human
        if features.noise_ratio < 0.15:
            flags.append("low_noise_ratio")
            human_score -= 0.2
        elif features.noise_ratio > 0.3:
            human_score += 0.2

        # correction_rate: < 0.05 → AI, > 0.1 → human
        if features.correction_rate < 0.05:
            flags.append("low_correction_rate")
            human_score -= 0.15
        elif features.correction_rate > 0.1:
            human_score += 0.15

        # smoothness: > 8.0 → AI, < 5.0 → human
        if features.smoothness > 8.0:
            flags.append("high_smoothness")
            human_score -= 0.15
        elif features.smoothness < 5.0:
            human_score += 0.15

        # Clamp
        human_score = max(0.0, min(1.0, human_score))
        ai_score = round(1.0 - human_score, 2)

        if human_score > 0.65:
            verdict = "human"
        elif human_score < 0.35:
            verdict = "ai"
        else:
            verdict = "uncertain"

        return MotorScore(
            trajectory_id=traj.id,
            features=features,
            human_score=human_score,
            ai_score=ai_score,
            verdict=verdict,
            flags=flags,
        )

    def batch_score(self, trajs: list[InputTrajectory]) -> list[MotorScore]:
        """Score multiple trajectories."""
        return [self.score(t) for t in trajs]
