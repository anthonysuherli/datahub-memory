"""Standalone stdio MCP server exposing datahub_memory's memory tools.

agent.py's MEMORY_SERVER is built with claude_agent_sdk's
create_sdk_mcp_server, which is in-process-only -- it hands the SDK's own
`query()` loop an object, not something a subprocess can speak to. A Claude
Code plugin's mcp.json needs a real child process talking MCP over stdio, so
this module wraps the SAME five tool handlers (memory_recall, memory_persist,
check_freshness, writeback_description, writeback_report) from agent.py in
the `mcp` package's FastMCP -- no bridge/writeback logic is reimplemented,
this just re-exposes agent.py's tool handlers over a different transport.

Run directly: `python -m datahub_memory.mcp_stub`
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Mirror __main__.py: pin DELAPAN_DB_PATH into this repo's .data/ before
# datahub_memory.agent (which pulls in delapan transitively via bridge.py) is
# imported, so a fresh clone doesn't silently write to ~/.delapan/delapan.db.
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / ".data" / "delapan.db"
os.environ.setdefault("DELAPAN_DB_PATH", str(_DEFAULT_DB_PATH))
Path(os.environ["DELAPAN_DB_PATH"]).parent.mkdir(parents=True, exist_ok=True)

from mcp.server.fastmcp import FastMCP

from datahub_memory import agent as agent_mod

mcp = FastMCP("datahub-memory")


async def _call(tool_obj: Any, args: dict) -> dict:
    """Invoke an SdkMcpTool's handler and unwrap its text-content envelope."""
    out = await tool_obj.handler(args)
    return json.loads(out["content"][0]["text"])


@mcp.tool()
async def memory_recall(project: str, kb: str, query: str) -> dict:
    """Tap the KB for prior grounded knowledge about a question."""
    return await _call(agent_mod.memory_recall, {"project": project, "kb": kb, "query": query})


@mcp.tool()
async def memory_persist(
    project: str, kb: str, question: str, conclusion: str, category: str, grounded: list
) -> dict:
    """Persist an investigation conclusion as a grounded finding."""
    return await _call(agent_mod.memory_persist, {
        "project": project, "kb": kb, "question": question,
        "conclusion": conclusion, "category": category, "grounded": grounded,
    })


@mcp.tool()
async def check_freshness(grounded: list) -> dict:
    """Deterministically check whether grounded DataHub entities have drifted
    since a finding was persisted: recompute each URN's snapshot_hash from its
    CURRENT schema fields + lineage and compare to the recorded hash."""
    return await _call(agent_mod.check_freshness, {"grounded": grounded})


@mcp.tool()
async def writeback_description(urn: str, description: str) -> dict:
    """Fallback only: fill an empty/stale dataset description in DataHub. Use
    this only if the DataHub MCP server's own update_description tool call
    failed."""
    return await _call(agent_mod.writeback_description, {"urn": urn, "description": description})


@mcp.tool()
async def writeback_report(urn: str, title: str, markdown: str) -> dict:
    """Fallback only: attach the investigation report to a DataHub entity. Use
    this only if the DataHub MCP server's own save_document tool call
    failed."""
    return await _call(agent_mod.writeback_report, {"urn": urn, "title": title, "markdown": markdown})


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
