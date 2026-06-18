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


if __name__ == "__main__":
    main()
