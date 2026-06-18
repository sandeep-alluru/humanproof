"""Tests for the Click CLI using CliRunner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from humanproof.cli import main
from humanproof.trajectory import InputSample, InputTrajectory


def make_trajectory_file(path: Path, session_id: str = "cli_test") -> Path:
    samples = [InputSample(dx=1.0, dy=1.0, dt=10.0) for _ in range(10)]
    traj = InputTrajectory(samples=samples, session_id=session_id)
    path.write_text(json.dumps(traj.to_dict()))
    return path


def test_cli_version() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "humanproof" in result.output.lower() or "0.1.0" in result.output


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "score" in result.output


def test_cli_score_command(tmp_path: Path) -> None:
    runner = CliRunner()
    f = make_trajectory_file(tmp_path / "traj.json")
    db = str(tmp_path / "test.db")
    result = runner.invoke(main, ["score", str(f), "--db", db])
    assert result.exit_code == 0


def test_cli_status_command(tmp_path: Path) -> None:
    runner = CliRunner()
    db = str(tmp_path / "status.db")
    result = runner.invoke(main, ["status", "--db", db])
    assert result.exit_code == 0
    assert "Trajectories" in result.output or "Scores" in result.output


def test_cli_log_empty(tmp_path: Path) -> None:
    runner = CliRunner()
    db = str(tmp_path / "empty.db")
    result = runner.invoke(main, ["log", "--db", db])
    assert result.exit_code == 0


def test_cli_batch_no_files(tmp_path: Path) -> None:
    runner = CliRunner()
    db = str(tmp_path / "batch.db")
    result = runner.invoke(main, ["batch", str(tmp_path), "--db", db])
    assert result.exit_code == 0
    assert "No JSON files" in result.output


def test_cli_batch_with_files(tmp_path: Path) -> None:
    runner = CliRunner()
    for i in range(3):
        make_trajectory_file(tmp_path / f"traj{i}.json", session_id=f"sess{i}")
    db = str(tmp_path / "batch.db")
    result = runner.invoke(main, ["batch", str(tmp_path), "--db", db])
    assert result.exit_code == 0
    assert "3" in result.output


def test_cli_score_then_log(tmp_path: Path) -> None:
    runner = CliRunner()
    f = make_trajectory_file(tmp_path / "traj.json")
    db = str(tmp_path / "shared.db")
    runner.invoke(main, ["score", str(f), "--db", db])
    result = runner.invoke(main, ["log", "--db", db])
    assert result.exit_code == 0
