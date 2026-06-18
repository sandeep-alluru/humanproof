"""MCP server for humanproof.

Start:  python -m humanproof.mcp_server
Or:     humanproof-mcp

Add to Claude Desktop:
    {
        "mcpServers": {
            "humanproof": {
                "command": "humanproof-mcp"
            }
        }
    }
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _require_mcp() -> Any:
    try:
        import mcp.server.stdio
        import mcp.types as types
        from mcp.server import Server as _Server

        return mcp, types, _Server
    except ImportError:
        print(
            "MCP server requires: pip install 'humanproof[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)


def run_server() -> None:
    """Start the MCP server on stdio."""
    mcp_mod, types, server_cls = _require_mcp()

    server = server_cls("humanproof")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="score_trajectory",
                description="Score a single input trajectory for human vs AI likelihood.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trajectory_dict": {
                            "type": "object",
                            "description": "Trajectory dict with 'samples' list.",
                        }
                    },
                    "required": ["trajectory_dict"],
                },
            ),
            types.Tool(
                name="batch_score",
                description="Score multiple input trajectories.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trajectory_dicts": {
                            "type": "array",
                            "description": "List of trajectory dicts.",
                        }
                    },
                    "required": ["trajectory_dicts"],
                },
            ),
            types.Tool(
                name="list_scores",
                description="List all stored scores from the humanproof store.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        from humanproof.scorer import MotorScorer
        from humanproof.store import HumanproofStore
        from humanproof.trajectory import InputTrajectory

        scorer = MotorScorer()
        store = HumanproofStore()

        if name == "score_trajectory":
            traj = InputTrajectory.from_dict(arguments["trajectory_dict"])
            result = scorer.score(traj)
            store.save_score(result)
            return [types.TextContent(type="text", text=json.dumps(result.to_dict()))]
        elif name == "batch_score":
            results = []
            for td in arguments["trajectory_dicts"]:
                traj = InputTrajectory.from_dict(td)
                result = scorer.score(traj)
                store.save_score(result)
                results.append(result.to_dict())
            return [types.TextContent(type="text", text=json.dumps(results))]
        elif name == "list_scores":
            scores = [s.to_dict() for s in store.list_scores()]
            return [types.TextContent(type="text", text=json.dumps(scores))]
        else:
            raise ValueError(f"Unknown tool: {name}")

    import asyncio

    async def _main() -> None:
        async with mcp_mod.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )

    asyncio.run(_main())


if __name__ == "__main__":
    run_server()
