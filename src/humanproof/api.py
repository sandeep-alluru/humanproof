"""FastAPI REST wrapper for humanproof.

Start:   uvicorn humanproof.api:app --reload
Install: pip install "humanproof[api]"
Docs:    http://localhost:8000/docs
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError as exc:
    raise ImportError("API server requires: pip install 'humanproof[api]'") from exc

from humanproof import __version__
from humanproof.scorer import MotorScorer
from humanproof.store import HumanproofStore
from humanproof.trajectory import InputTrajectory

app = FastAPI(
    title="humanproof API",
    description="Motor-noise fingerprinting for AI detection in competitive games.",
    version=__version__,
    license_info={
        "name": "MIT",
        "url": "https://github.com/sandeep-alluru/humanproof/blob/main/LICENSE",
    },
)

_scorer = MotorScorer()
_store = HumanproofStore()


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": __version__, "service": "humanproof"}


@app.post("/score")
def score_trajectory(trajectory_dict: dict[str, Any]) -> dict[str, Any]:
    """Score a single trajectory."""
    try:
        traj = InputTrajectory.from_dict(trajectory_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    result = _scorer.score(traj)
    _store.save_trajectory(traj)
    _store.save_score(result)
    return result.to_dict()


@app.post("/batch")
def batch_score(trajectory_dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score multiple trajectories."""
    results = []
    for td in trajectory_dicts:
        try:
            traj = InputTrajectory.from_dict(td)
            result = _scorer.score(traj)
            _store.save_trajectory(traj)
            _store.save_score(result)
            results.append(result.to_dict())
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
    return results


@app.get("/scores")
def list_scores() -> list[dict[str, Any]]:
    """Return all stored scores."""
    return [s.to_dict() for s in _store.list_scores()]
