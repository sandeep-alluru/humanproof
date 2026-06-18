"""SQLite-backed store for trajectories and scores."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from humanproof.scorer import MotorFeatures, MotorScore
from humanproof.trajectory import InputTrajectory

_DEFAULT_DB = Path.home() / ".humanproof" / "store.db"


class HumanproofStore:
    """Persist trajectories and scores to SQLite.

    Attributes:
        path: Path to the SQLite database file.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        """Initialize store and create tables if needed."""
        self.path = Path(path) if path is not None else _DEFAULT_DB
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trajectories (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                trajectory_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def save_trajectory(self, traj: InputTrajectory) -> None:
        """Save a trajectory (upsert)."""
        self._conn.execute(
            "INSERT OR REPLACE INTO trajectories (id, data) VALUES (?, ?)",
            (traj.id, json.dumps(traj.to_dict())),
        )
        self._conn.commit()

    def get_trajectory(self, traj_id: str) -> InputTrajectory | None:
        """Retrieve a trajectory by ID."""
        row = self._conn.execute(
            "SELECT data FROM trajectories WHERE id = ?", (traj_id,)
        ).fetchone()
        if row is None:
            return None
        return InputTrajectory.from_dict(json.loads(row[0]))

    def save_score(self, score: MotorScore) -> None:
        """Save a MotorScore (upsert)."""
        self._conn.execute(
            "INSERT OR REPLACE INTO scores (trajectory_id, data) VALUES (?, ?)",
            (score.trajectory_id, json.dumps(score.to_dict())),
        )
        self._conn.commit()

    def get_score(self, trajectory_id: str) -> MotorScore | None:
        """Retrieve a MotorScore by trajectory ID."""
        row = self._conn.execute(
            "SELECT data FROM scores WHERE trajectory_id = ?", (trajectory_id,)
        ).fetchone()
        if row is None:
            return None
        return _score_from_dict(json.loads(row[0]))

    def list_scores(self) -> list[MotorScore]:
        """Return all stored MotorScores."""
        rows = self._conn.execute("SELECT data FROM scores").fetchall()
        return [_score_from_dict(json.loads(row[0])) for row in rows]

    def trajectory_count(self) -> int:
        """Return count of stored trajectories."""
        row = self._conn.execute("SELECT COUNT(*) FROM trajectories").fetchone()
        return int(row[0])

    def score_count(self) -> int:
        """Return count of stored scores."""
        row = self._conn.execute("SELECT COUNT(*) FROM scores").fetchone()
        return int(row[0])

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()


def _score_from_dict(d: dict[str, Any]) -> MotorScore:
    """Deserialize a MotorScore from a dict."""
    fd = d["features"]
    features = MotorFeatures(
        mean_speed=fd["mean_speed"],
        speed_std=fd["speed_std"],
        noise_ratio=fd["noise_ratio"],
        correction_rate=fd["correction_rate"],
        jerk_mean=fd["jerk_mean"],
        jerk_std=fd["jerk_std"],
        max_speed=fd["max_speed"],
        smoothness=fd["smoothness"],
    )
    return MotorScore(
        trajectory_id=d["trajectory_id"],
        features=features,
        human_score=d["human_score"],
        ai_score=d["ai_score"],
        verdict=d["verdict"],
        flags=d["flags"],
    )
