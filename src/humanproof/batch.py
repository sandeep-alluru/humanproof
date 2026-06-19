"""Batch scoring utilities for humanproof."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from humanproof.scorer import MotorScore, MotorScorer
from humanproof.trajectory import InputSample, InputTrajectory


@dataclass
class BatchScoreResult:
    scores: list[MotorScore]
    human_count: int
    ai_count: int
    uncertain_count: int
    mean_human_score: float
    flagged_trajectories: list[str]   # IDs where verdict == "ai"
    summary: str

    def to_dict(self):
        return {
            "human_count": self.human_count,
            "ai_count": self.ai_count,
            "uncertain_count": self.uncertain_count,
            "mean_human_score": self.mean_human_score,
            "flagged_trajectories": self.flagged_trajectories,
            "summary": self.summary,
            "scores": [s.to_dict() for s in self.scores],
        }


def batch_score(
    trajectories: list[InputTrajectory], scorer: MotorScorer | None = None
) -> BatchScoreResult:
    """Score a list of trajectories and return aggregated BatchScoreResult."""
    if scorer is None:
        scorer = MotorScorer()
    scores = scorer.batch_score(trajectories)
    human_count = sum(1 for s in scores if s.verdict == "human")
    ai_count = sum(1 for s in scores if s.verdict == "ai")
    uncertain_count = sum(1 for s in scores if s.verdict == "uncertain")
    mean_human_score = sum(s.human_score for s in scores) / len(scores) if scores else 0.0
    flagged = [s.trajectory_id for s in scores if s.verdict == "ai"]
    total = len(scores)
    summary = (
        f"Scored {total} trajectories: {human_count} human, {ai_count} AI, "
        f"{uncertain_count} uncertain. Mean human score: {mean_human_score:.2f}."
    )
    return BatchScoreResult(
        scores=scores,
        human_count=human_count,
        ai_count=ai_count,
        uncertain_count=uncertain_count,
        mean_human_score=mean_human_score,
        flagged_trajectories=flagged,
        summary=summary,
    )


def score_from_csv(csv_path: Path) -> BatchScoreResult:
    """Load trajectories from CSV (columns: trajectory_id,t,x,y,button) and score them.

    Each unique trajectory_id forms one InputTrajectory. Rows are sorted by t.
    x,y are treated as absolute positions; dx/dy are computed from consecutive rows.
    button column is ignored (reserved for future use).
    """
    csv_path = Path(csv_path)
    rows_by_id: dict[str, list[dict]] = {}
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = row["trajectory_id"]
            rows_by_id.setdefault(tid, []).append(row)

    trajectories: list[InputTrajectory] = []
    for tid, rows in rows_by_id.items():
        rows.sort(key=lambda r: float(r["t"]))
        samples: list[InputSample] = []
        prev_x: float | None = None
        prev_y: float | None = None
        prev_t: float | None = None
        for r in rows:
            x = float(r["x"])
            y = float(r["y"])
            t = float(r["t"])
            if prev_x is None:
                prev_x, prev_y, prev_t = x, y, t
                continue
            dx = x - prev_x
            dy = y - (prev_y or 0.0)
            dt = t - (prev_t or 0.0)
            if dt <= 0:
                dt = 1.0
            samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=t))
            prev_x, prev_y, prev_t = x, y, t
        if len(samples) >= 1:
            traj = InputTrajectory(samples=samples, session_id=tid)
            trajectories.append(traj)

    return batch_score(trajectories)
