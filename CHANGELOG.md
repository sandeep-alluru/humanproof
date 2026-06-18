# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
