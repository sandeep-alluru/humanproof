"""Click CLI for humanproof."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from humanproof import __version__
from humanproof import report as rpt
from humanproof.scorer import MotorScorer
from humanproof.store import HumanproofStore
from humanproof.trajectory import InputTrajectory

console = Console()


@click.group()
@click.version_option(__version__, prog_name="humanproof")
def main() -> None:
    """humanproof — motor-noise fingerprinting for AI detection."""


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--db", default=None, help="Path to store database.")
def score(file: str, db: str | None) -> None:
    """Score a JSON trajectory file."""
    path = Path(file)
    data = json.loads(path.read_text())
    traj = InputTrajectory.from_dict(data)
    scorer = MotorScorer()
    result = scorer.score(traj)
    rpt.print_score(result, console=console)
    store = HumanproofStore(db)
    store.save_trajectory(traj)
    store.save_score(result)
    store.close()


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--db", default=None, help="Path to store database.")
def batch(directory: str, db: str | None) -> None:
    """Score all JSON trajectory files in a directory."""
    dir_path = Path(directory)
    files = sorted(dir_path.glob("*.json"))
    if not files:
        console.print("[yellow]No JSON files found.[/yellow]")
        return
    scorer = MotorScorer()
    store = HumanproofStore(db)
    results = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            traj = InputTrajectory.from_dict(data)
            result = scorer.score(traj)
            results.append(result)
            rpt.print_score(result, console=console)
            store.save_trajectory(traj)
            store.save_score(result)
        except Exception as e:
            console.print(f"[red]Error processing {f.name}: {e}[/red]")
    store.close()
    console.print(f"\n[bold]Scored {len(results)} trajectories.[/bold]")


@main.command(name="log")
@click.option("--db", default=None, help="Path to store database.")
def log_cmd(db: str | None) -> None:
    """List all stored scores."""
    store = HumanproofStore(db)
    scores = store.list_scores()
    store.close()
    if not scores:
        console.print("[yellow]No scores stored yet.[/yellow]")
        return
    console.print(rpt.to_markdown(scores))


@main.command()
@click.option("--db", default=None, help="Path to store database.")
def status(db: str | None) -> None:
    """Show count of stored trajectories and scores."""
    store = HumanproofStore(db)
    tc = store.trajectory_count()
    sc = store.score_count()
    store.close()
    console.print(f"[bold]Trajectories:[/bold] {tc}")
    console.print(f"[bold]Scores:[/bold]       {sc}")


@main.command("batch-csv")
@click.argument("csv_file", type=click.Path(exists=True))
def batch_csv(csv_file: str) -> None:
    """Score trajectories from a CSV file (columns: trajectory_id,t,x,y,button)."""
    from humanproof.batch import score_from_csv

    result = score_from_csv(Path(csv_file))
    console.print(result.summary)
    console.print(f"  Human:     {result.human_count}")
    console.print(f"  AI:        {result.ai_count}")
    console.print(f"  Uncertain: {result.uncertain_count}")
    if result.flagged_trajectories:
        console.print(f"  [red]Flagged:[/red] {', '.join(result.flagged_trajectories)}")


@main.command("session")
@click.argument("csv_file", type=click.Path(exists=True))
@click.option("--session-id", default="session", show_default=True, help="Session identifier.")
def session_cmd(csv_file: str, session_id: str) -> None:
    """Analyze a session from a CSV file for behavioral shifts."""
    # Reuse score_from_csv to load trajectories but we need them as objects
    # Load raw trajectories then analyze
    import csv as _csv

    from humanproof.session import analyze_session
    from humanproof.trajectory import InputSample, InputTrajectory

    rows_by_id: dict[str, list[dict]] = {}
    with open(csv_file, newline="") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            tid = row["trajectory_id"]
            rows_by_id.setdefault(tid, []).append(row)

    trajectories = []
    for tid, rows in rows_by_id.items():
        rows.sort(key=lambda r: float(r["t"]))
        samples = []
        prev_x = prev_y = prev_t = None
        for r in rows:
            x, y, t = float(r["x"]), float(r["y"]), float(r["t"])
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
        if samples:
            trajectories.append(InputTrajectory(samples=samples, session_id=tid))

    analysis = analyze_session(session_id, trajectories)
    console.print(f"[bold]Session:[/bold] {analysis.session_id}")
    console.print(f"  Trajectories: {analysis.trajectory_count}")
    console.print(f"  Mean human score: {analysis.mean_human_score:.2f}")
    console.print(f"  Verdict: [bold]{analysis.verdict}[/bold]")
    console.print(f"  Risk level: [bold]{analysis.risk_level}[/bold]")
    if analysis.behavioral_shift_detected:
        console.print(f"  [red]Behavioral shift at index {analysis.shift_at_index}[/red]")


if __name__ == "__main__":
    main()
