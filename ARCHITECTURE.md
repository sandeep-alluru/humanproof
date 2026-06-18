# Architecture

## Data Flow

```
InputSample(dx, dy, dt, timestamp)
        │
        ▼
InputTrajectory(samples, session_id)
        │
        ├── velocity_profile()      → [pixels/ms per sample]
        ├── acceleration_profile()  → [pixels/ms² per step]
        ├── jerk_profile()          → [pixels/ms³ per step]
        ├── correction_count()      → int (direction reversals)
        └── noise_ratio()           → float (std/mean speed)
        │
        ▼
MotorScorer.extract_features(traj)
        │
        ▼
MotorFeatures(mean_speed, speed_std, noise_ratio, correction_rate,
              jerk_mean, jerk_std, max_speed, smoothness)
        │
        ▼
MotorScorer.score(traj)
        │
        ▼
MotorScore(trajectory_id, features, human_score, ai_score, verdict, flags)
        │
        ├── CLI (cli.py)          → Rich terminal output
        ├── REST API (api.py)     → JSON via FastAPI
        └── MCP (mcp_server.py)  → Claude tool calls
```

## Module Map

| Module | Responsibility |
|---|---|
| `trajectory.py` | Core data model: `InputSample`, `InputTrajectory` with kinematic profiles |
| `scorer.py` | Feature extraction (`MotorFeatures`) and threshold-based scoring (`MotorScore`, `MotorScorer`) |
| `store.py` | SQLite persistence via `HumanproofStore` |
| `report.py` | Output formatters: Rich terminal, JSON, Markdown |
| `cli.py` | Click CLI: `score`, `batch`, `log`, `status` |
| `api.py` | FastAPI REST server: `/health`, `/score`, `/batch`, `/scores` |
| `mcp_server.py` | MCP stdio server: `score_trajectory`, `batch_score`, `list_scores` |

## SQLite Schema

```sql
CREATE TABLE trajectories (
    id   TEXT PRIMARY KEY,   -- SHA-256[:16] of session/samples fingerprint
    data TEXT NOT NULL       -- JSON: {session_id, samples: [{dx,dy,dt,timestamp}]}
);

CREATE TABLE scores (
    trajectory_id TEXT PRIMARY KEY,
    data          TEXT NOT NULL   -- JSON: {trajectory_id, features, human_score, ai_score, verdict, flags}
);
```

Default database location: `~/.humanproof/store.db`

## Scoring Algorithm

The scorer uses additive threshold heuristics (no ML model required):

```
human_score = 0.5  (prior)

if noise_ratio < 0.15:     human_score -= 0.20  # flag: low_noise_ratio
elif noise_ratio > 0.30:   human_score += 0.20

if correction_rate < 0.05: human_score -= 0.15  # flag: low_correction_rate
elif correction_rate > 0.10: human_score += 0.15

if smoothness > 8.0:       human_score -= 0.15  # flag: high_smoothness
elif smoothness < 5.0:     human_score += 0.15

human_score = clamp(human_score, 0.0, 1.0)
ai_score    = 1.0 - human_score

verdict = "human" if human_score > 0.65
        | "ai"    if human_score < 0.35
        | "uncertain"
```

`smoothness = 1 / (mean_abs_jerk + 1e-9)` — unbounded above for perfectly smooth AI input.
