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

try:
    import mcp.server.stdio as _mcp_stdio
    import mcp.types as _mcp_types
    from mcp.server import Server as _Server
    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False


def run_server() -> None:
    """Start the MCP server on stdio."""
    if not _HAS_MCP:
        print(
            "MCP server requires: pip install 'humanproof[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)

    server = _Server("humanproof")

    @server.list_tools()
    async def list_tools() -> list[_mcp_types.Tool]:
        return [
            _mcp_types.Tool(
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
            _mcp_types.Tool(
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
            _mcp_types.Tool(
                name="list_scores",
                description="List all stored scores from the humanproof store.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[_mcp_types.TextContent]:
        from humanproof.scorer import MotorScorer
        from humanproof.store import HumanproofStore
        from humanproof.trajectory import InputTrajectory

        scorer = MotorScorer()
        store = HumanproofStore()

        if name == "score_trajectory":
            traj = InputTrajectory.from_dict(arguments["trajectory_dict"])
            result = scorer.score(traj)
            store.save_score(result)
            return [_mcp_types.TextContent(type="text", text=json.dumps(result.to_dict()))]
        elif name == "batch_score":
            results = []
            for td in arguments["trajectory_dicts"]:
                traj = InputTrajectory.from_dict(td)
                result = scorer.score(traj)
                store.save_score(result)
                results.append(result.to_dict())
            return [_mcp_types.TextContent(type="text", text=json.dumps(results))]
        elif name == "list_scores":
            scores = [s.to_dict() for s in store.list_scores()]
            return [_mcp_types.TextContent(type="text", text=json.dumps(scores))]
        else:
            raise ValueError(f"Unknown tool: {name}")

    import asyncio

    async def _main() -> None:
        async with _mcp_stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )

    asyncio.run(_main())


if __name__ == "__main__":
    run_server()
