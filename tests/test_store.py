"""Tests for HumanproofStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from humanproof.scorer import MotorScorer
from humanproof.store import HumanproofStore
from humanproof.trajectory import InputSample, InputTrajectory


def make_traj(session_id: str = "test") -> InputTrajectory:
    samples = [InputSample(dx=1.0, dy=1.0, dt=10.0) for _ in range(5)]
    return InputTrajectory(samples=samples, session_id=session_id)


@pytest.fixture
def store(tmp_path: Path):
    db_path = tmp_path / "test.db"
    s = HumanproofStore(path=db_path)
    yield s
    s.close()


def test_store_creates_db(tmp_path: Path) -> None:
    db_path = tmp_path / "new.db"
    store = HumanproofStore(path=db_path)
    assert db_path.exists()
    store.close()


def test_save_and_get_trajectory(store: HumanproofStore) -> None:
    traj = make_traj("session1")
    store.save_trajectory(traj)
    retrieved = store.get_trajectory(traj.id)
    assert retrieved is not None
    assert retrieved.id == traj.id


def test_get_trajectory_missing(store: HumanproofStore) -> None:
    result = store.get_trajectory("nonexistent_id")
    assert result is None


def test_save_and_get_score(store: HumanproofStore) -> None:
    traj = make_traj("session2")
    scorer = MotorScorer()
    score = scorer.score(traj)
    store.save_score(score)
    retrieved = store.get_score(traj.id)
    assert retrieved is not None
    assert retrieved.trajectory_id == traj.id
    assert retrieved.verdict in ("human", "ai", "uncertain")


def test_get_score_missing(store: HumanproofStore) -> None:
    result = store.get_score("nonexistent")
    assert result is None


def test_list_scores_empty(store: HumanproofStore) -> None:
    assert store.list_scores() == []


def test_list_scores_multiple(store: HumanproofStore) -> None:
    scorer = MotorScorer()
    for i in range(3):
        traj = make_traj(f"sess{i}")
        score = scorer.score(traj)
        store.save_score(score)
    scores = store.list_scores()
    assert len(scores) == 3


def test_trajectory_count(store: HumanproofStore) -> None:
    assert store.trajectory_count() == 0
    store.save_trajectory(make_traj("a"))
    store.save_trajectory(make_traj("b"))
    assert store.trajectory_count() == 2


def test_score_count(store: HumanproofStore) -> None:
    scorer = MotorScorer()
    assert store.score_count() == 0
    traj = make_traj("count_test")
    store.save_score(scorer.score(traj))
    assert store.score_count() == 1


def test_save_trajectory_upsert(store: HumanproofStore) -> None:
    traj = make_traj("upsert_test")
    store.save_trajectory(traj)
    store.save_trajectory(traj)
    assert store.trajectory_count() == 1


def test_score_roundtrip_values(store: HumanproofStore) -> None:
    traj = make_traj("roundtrip")
    scorer = MotorScorer()
    score = scorer.score(traj)
    store.save_score(score)
    retrieved = store.get_score(traj.id)
    assert retrieved is not None
    assert abs(retrieved.human_score - score.human_score) < 1e-9
    assert abs(retrieved.ai_score - score.ai_score) < 1e-9
    assert retrieved.flags == score.flags
