"""Output formatters for MotorScore results."""

from __future__ import annotations

import json
from typing import Any

from humanproof.scorer import MotorScore


def print_score(score: MotorScore, console: Any = None) -> None:
    """Print a MotorScore to the terminal using Rich."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        c = console or Console()

        color = {
            "human": "green",
            "ai": "red",
            "uncertain": "yellow",
        }.get(score.verdict, "white")

        c.print(
            Panel(
                f"[bold {color}]{score.verdict.upper()}[/bold {color}]  "
                f"human={score.human_score:.2f}  ai={score.ai_score:.2f}",
                title=f"[bold]humanproof[/bold] · {score.trajectory_id}",
            )
        )

        t = Table(show_header=True, header_style="bold cyan")
        t.add_column("Feature", style="dim")
        t.add_column("Value", justify="right")
        for k, v in score.features.to_dict().items():
            t.add_row(k, f"{v:.4f}")
        c.print(t)

        if score.flags:
            c.print(f"[yellow]Flags:[/yellow] {', '.join(score.flags)}")
    except ImportError:
        print(f"trajectory_id={score.trajectory_id}")
        print(f"verdict={score.verdict}  human={score.human_score:.2f}  ai={score.ai_score:.2f}")
        if score.flags:
            print(f"flags={', '.join(score.flags)}")


def to_json(scores: list[MotorScore]) -> str:
    """Serialize a list of MotorScores to a JSON string."""
    return json.dumps([s.to_dict() for s in scores], indent=2)


def to_markdown(scores: list[MotorScore]) -> str:
    """Format a list of MotorScores as a Markdown table."""
    if not scores:
        return "No scores."

    header = "| ID | Verdict | Human | AI | Flags |\n|---|---|---|---|---|\n"
    rows = []
    for s in scores:
        flags = ", ".join(s.flags) if s.flags else "-"
        rows.append(
            f"| {s.trajectory_id} | {s.verdict} "
            f"| {s.human_score:.2f} | {s.ai_score:.2f} | {flags} |"
        )
    return header + "\n".join(rows)
