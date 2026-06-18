"""Tests for report formatters."""

from __future__ import annotations

import json
import pytest
from humanproof.scorer import MotorFeatures, MotorScore
from humanproof.report import print_score, to_json, to_markdown


def make_score(
    traj_id: str = "abc123",
    verdict: str = "human",
    human_score: float = 0.8,
    flags: list[str] | None = None,
) -> MotorScore:
    features = MotorFeatures(
        mean_speed=1.0,
        speed_std=0.5,
        noise_ratio=0.5,
        correction_rate=0.2,
        jerk_mean=0.1,
        jerk_std=0.05,
        max_speed=2.0,
        smoothness=10.0,
    )
    return MotorScore(
        trajectory_id=traj_id,
        features=features,
        human_score=human_score,
        ai_score=1.0 - human_score,
        verdict=verdict,
        flags=flags or [],
    )


def test_to_json_empty() -> None:
    result = to_json([])
    assert result == "[]"


def test_to_json_single_score() -> None:
    score = make_score()
    result = to_json([score])
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["trajectory_id"] == "abc123"
    assert data[0]["verdict"] == "human"


def test_to_json_multiple_scores() -> None:
    scores = [make_score("id1", "ai", 0.2), make_score("id2", "human", 0.9)]
    result = to_json(scores)
    data = json.loads(result)
    assert len(data) == 2


def test_to_json_has_features() -> None:
    score = make_score()
    result = to_json([score])
    data = json.loads(result)
    assert "features" in data[0]
    assert "noise_ratio" in data[0]["features"]


def test_to_markdown_empty() -> None:
    result = to_markdown([])
    assert "No scores" in result


def test_to_markdown_header_row() -> None:
    result = to_markdown([make_score()])
    assert "Verdict" in result
    assert "Human" in result
    assert "AI" in result


def test_to_markdown_contains_id() -> None:
    score = make_score("unique_traj_id")
    result = to_markdown([score])
    assert "unique_traj_id" in result


def test_to_markdown_shows_flags() -> None:
    score = make_score(flags=["low_noise_ratio", "high_smoothness"])
    result = to_markdown([score])
    assert "low_noise_ratio" in result


def test_print_score_runs_without_error() -> None:
    from rich.console import Console
    from io import StringIO
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    score = make_score()
    print_score(score, console=c)
    output = buf.getvalue()
    assert len(output) > 0


def test_print_score_ai_verdict() -> None:
    from rich.console import Console
    from io import StringIO
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    score = make_score("ai_traj", "ai", 0.1)
    print_score(score, console=c)
    output = buf.getvalue()
    assert len(output) > 0
