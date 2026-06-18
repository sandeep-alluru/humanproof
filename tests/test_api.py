"""Tests for the FastAPI REST server."""

from __future__ import annotations

import pytest

try:
    import fastapi  # noqa: F401
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")


def get_client():
    from humanproof.api import app
    return TestClient(app)


def make_trajectory_dict(
    n: int = 10, dx: float = 1.0, dy: float = 1.0, session_id: str = "api_test"
) -> dict:
    return {
        "session_id": session_id,
        "samples": [{"dx": dx, "dy": dy, "dt": 10.0} for _ in range(n)],
    }


def test_health_endpoint() -> None:
    client = get_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "humanproof"


def test_score_endpoint() -> None:
    client = get_client()
    resp = client.post("/score", json=make_trajectory_dict())
    assert resp.status_code == 200
    data = resp.json()
    assert "trajectory_id" in data
    assert "verdict" in data
    assert "human_score" in data


def test_score_endpoint_returns_valid_verdict() -> None:
    client = get_client()
    resp = client.post("/score", json=make_trajectory_dict())
    data = resp.json()
    assert data["verdict"] in ("human", "ai", "uncertain")


def test_batch_endpoint() -> None:
    client = get_client()
    trajs = [make_trajectory_dict(session_id=f"batch_{i}") for i in range(3)]
    resp = client.post("/batch", json=trajs)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


def test_scores_endpoint() -> None:
    client = get_client()
    resp = client.get("/scores")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_score_invalid_payload() -> None:
    client = get_client()
    resp = client.post("/score", json={"bad": "payload"})
    assert resp.status_code in (422, 500)


def test_batch_empty() -> None:
    client = get_client()
    resp = client.post("/batch", json=[])
    assert resp.status_code == 200
    assert resp.json() == []
