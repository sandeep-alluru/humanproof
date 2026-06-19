# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `BatchScoreResult` dataclass and `batch_score()` function for scoring multiple trajectories at once
- `score_from_csv()` for loading and scoring trajectories from a CSV file (columns: trajectory_id,t,x,y,button)
- `SessionAnalysis` dataclass and `analyze_session()` for temporal behavioral analysis of gaming sessions
- `detect_shift()` for detecting aimbot-style behavioral changes across a sequence of trajectories
- `CalibrationResult` dataclass, `calibrate()` for grid-search threshold optimization from labeled examples
- `apply_calibration()` to produce a calibrated `MotorScorer` from a `CalibrationResult`
- CLI commands: `humanproof batch-csv <csv_file>` and `humanproof session <csv_file>`
- Tests: `tests/test_batch.py`, `tests/test_session.py`, `tests/test_calibration.py`

## [0.1.0] - 2026-06-18

### Added
- Core data model: `InputSample`, `InputTrajectory` with velocity/acceleration/jerk/noise profiles
- `MotorScorer` with threshold-based heuristics for human vs AI detection (no ML model required)
- `MotorFeatures` and `MotorScore` dataclasses with full serialization support
- SQLite-backed `HumanproofStore` for persisting trajectories and scores
- Rich terminal output, JSON, and Markdown report formatters
- Click CLI: `score`, `batch`, `log`, `status` subcommands
- FastAPI REST server: `/health`, `/score`, `/batch`, `/scores` endpoints
- MCP stdio server with `score_trajectory`, `batch_score`, `list_scores` tools
- 77 pytest tests with 95% coverage
- GitHub Action for CI trajectory scoring
- OpenAI function definitions, OpenAPI 3.0 spec, and agent config files (CLAUDE.md, AGENTS.md, CODEX.md)
- MkDocs documentation site with 11 pages

[Unreleased]: https://github.com/sandeep-alluru/humanproof/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sandeep-alluru/humanproof/releases/tag/v0.1.0
