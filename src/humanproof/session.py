"""Session-level analysis for humanproof — detect behavioral shifts (e.g. aimbot activation)."""

from __future__ import annotations

from dataclasses import dataclass

from humanproof.batch import batch_score
from humanproof.scorer import MotorScorer
from humanproof.trajectory import InputTrajectory


@dataclass
class SessionAnalysis:
    session_id: str
    trajectory_count: int
    mean_human_score: float
    score_over_time: list[tuple[int, float]]   # (trajectory_index, human_score)
    behavioral_shift_detected: bool
    shift_at_index: int | None   # where the score changed significantly
    verdict: str   # "consistent_human", "consistent_ai", "behavioral_shift"
    risk_level: str  # "low", "medium", "high"

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "trajectory_count": self.trajectory_count,
            "mean_human_score": self.mean_human_score,
            "score_over_time": self.score_over_time,
            "behavioral_shift_detected": self.behavioral_shift_detected,
            "shift_at_index": self.shift_at_index,
            "verdict": self.verdict,
            "risk_level": self.risk_level,
        }


def detect_shift(scores: list[float], window: int = 3, threshold: float = 0.3) -> int | None:
    """Detect the index where mean score changed by more than threshold.

    Compares the mean of the window before vs after each index.
    Returns the first index where the shift exceeds the threshold.
    """
    n = len(scores)
    if n < window * 2:
        return None
    for i in range(window, n - window + 1):
        before = scores[max(0, i - window) : i]
        after = scores[i : i + window]
        mean_before = sum(before) / len(before)
        mean_after = sum(after) / len(after)
        if abs(mean_after - mean_before) > threshold:
            return i
    return None


def analyze_session(session_id: str, trajectories: list[InputTrajectory]) -> SessionAnalysis:
    """Analyze a gaming session consisting of multiple trajectories."""
    scorer = MotorScorer()
    result = batch_score(trajectories, scorer=scorer)

    human_scores = [s.human_score for s in result.scores]
    score_over_time = [(i, human_scores[i]) for i in range(len(human_scores))]

    shift_idx = detect_shift(human_scores)
    behavioral_shift_detected = shift_idx is not None

    mean_score = result.mean_human_score

    if behavioral_shift_detected:
        verdict = "behavioral_shift"
        risk_level = "high"
    elif mean_score >= 0.65:
        verdict = "consistent_human"
        risk_level = "low"
    elif mean_score <= 0.35:
        verdict = "consistent_ai"
        risk_level = "high"
    else:
        verdict = "consistent_human"
        risk_level = "medium"

    return SessionAnalysis(
        session_id=session_id,
        trajectory_count=len(trajectories),
        mean_human_score=mean_score,
        score_over_time=score_over_time,
        behavioral_shift_detected=behavioral_shift_detected,
        shift_at_index=shift_idx,
        verdict=verdict,
        risk_level=risk_level,
    )
