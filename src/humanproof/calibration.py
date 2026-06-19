"""Calibration utilities — find optimal decision thresholds from labeled examples."""

from __future__ import annotations

from dataclasses import dataclass

from humanproof.scorer import MotorScorer
from humanproof.trajectory import InputTrajectory


@dataclass
class CalibrationResult:
    optimal_noise_threshold: float
    optimal_correction_threshold: float
    accuracy: float
    human_precision: float
    ai_precision: float

    def to_dict(self):
        return {
            "optimal_noise_threshold": self.optimal_noise_threshold,
            "optimal_correction_threshold": self.optimal_correction_threshold,
            "accuracy": self.accuracy,
            "human_precision": self.human_precision,
            "ai_precision": self.ai_precision,
        }


def _evaluate(
    human_trajs: list[InputTrajectory],
    ai_trajs: list[InputTrajectory],
    noise_threshold: float,
    correction_threshold: float,
) -> tuple[float, float, float]:
    """Evaluate a scorer with custom thresholds.

    Returns (accuracy, human_precision, ai_precision).
    """
    scorer = MotorScorer()

    def predict(traj: InputTrajectory) -> str:
        features = scorer.extract_features(traj)
        human_score = 0.5
        if features.noise_ratio < noise_threshold:
            human_score -= 0.2
        elif features.noise_ratio > noise_threshold * 2:
            human_score += 0.2
        if features.correction_rate < correction_threshold:
            human_score -= 0.15
        elif features.correction_rate > correction_threshold * 2:
            human_score += 0.15
        if features.smoothness > 8.0:
            human_score -= 0.15
        elif features.smoothness < 5.0:
            human_score += 0.15
        human_score = max(0.0, min(1.0, human_score))
        if human_score > 0.65:
            return "human"
        elif human_score < 0.35:
            return "ai"
        return "uncertain"

    correct = 0
    human_tp = 0
    human_predicted = 0
    ai_tp = 0
    ai_predicted = 0
    total = len(human_trajs) + len(ai_trajs)

    for traj in human_trajs:
        pred = predict(traj)
        if pred == "human":
            correct += 1
            human_tp += 1
            human_predicted += 1
        elif pred == "uncertain":
            # Partial credit: treat uncertain as neither right nor wrong
            correct += 0
            human_predicted += 0
        else:
            ai_predicted += 1

    for traj in ai_trajs:
        pred = predict(traj)
        if pred == "ai":
            correct += 1
            ai_tp += 1
            ai_predicted += 1
        elif pred == "uncertain":
            correct += 0
        else:
            human_predicted += 1

    accuracy = correct / total if total > 0 else 0.0
    human_precision = human_tp / human_predicted if human_predicted > 0 else 0.0
    ai_precision = ai_tp / ai_predicted if ai_predicted > 0 else 0.0

    return accuracy, human_precision, ai_precision


def calibrate(
    human_trajectories: list[InputTrajectory],
    ai_trajectories: list[InputTrajectory],
) -> CalibrationResult:
    """Find optimal decision thresholds via grid search over noise and correction thresholds."""
    noise_candidates = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    correction_candidates = [0.03, 0.05, 0.08, 0.10, 0.12, 0.15]

    best_accuracy = -1.0
    best_noise = 0.15
    best_correction = 0.05
    best_human_precision = 0.0
    best_ai_precision = 0.0

    for noise_t in noise_candidates:
        for corr_t in correction_candidates:
            acc, hp, ap = _evaluate(human_trajectories, ai_trajectories, noise_t, corr_t)
            if acc > best_accuracy:
                best_accuracy = acc
                best_noise = noise_t
                best_correction = corr_t
                best_human_precision = hp
                best_ai_precision = ap

    return CalibrationResult(
        optimal_noise_threshold=best_noise,
        optimal_correction_threshold=best_correction,
        accuracy=best_accuracy,
        human_precision=best_human_precision,
        ai_precision=best_ai_precision,
    )


def apply_calibration(scorer: MotorScorer, calibration: CalibrationResult) -> MotorScorer:
    """Return a new MotorScorer with calibrated thresholds patched in."""
    import types

    new_scorer = MotorScorer()
    noise_threshold = calibration.optimal_noise_threshold
    correction_threshold = calibration.optimal_correction_threshold

    def _calibrated_score(self, traj: InputTrajectory):  # type: ignore[override]
        from humanproof.scorer import MotorScore
        features = self.extract_features(traj)
        flags = []
        human_score = 0.5
        if features.noise_ratio < noise_threshold:
            flags.append("low_noise_ratio")
            human_score -= 0.2
        elif features.noise_ratio > noise_threshold * 2:
            human_score += 0.2
        if features.correction_rate < correction_threshold:
            flags.append("low_correction_rate")
            human_score -= 0.15
        elif features.correction_rate > correction_threshold * 2:
            human_score += 0.15
        if features.smoothness > 8.0:
            flags.append("high_smoothness")
            human_score -= 0.15
        elif features.smoothness < 5.0:
            human_score += 0.15
        human_score = max(0.0, min(1.0, human_score))
        ai_score = 1.0 - human_score
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

    new_scorer.score = types.MethodType(_calibrated_score, new_scorer)
    return new_scorer
