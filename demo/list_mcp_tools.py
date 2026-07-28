"""List tools exposed by `mcp-server-datahub` over stdio MCP.

Speaks the MCP handshake (initialize -> notifications/initialized -> tools/list)
against `uvx mcp-server-datahub` and prints the tool names it advertises. Used to
empirically check which tools appear against self-hosted OSS DataHub, with and
without TOOLS_IS_MUTATION_ENABLED=true (see docs/R1-decision.md).

Usage:
    .venv/bin/python demo/list_mcp_tools.py
    TOOLS_IS_MUTATION_ENABLED=true .venv/bin/python demo/list_mcp_tools.py

Requires DATAHUB_GMS_URL (and DATAHUB_GMS_TOKEN if auth is enabled) in the
environment -- source .env.local first.
"""

from __future__ import annotations

import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    env = dict(os.environ)
    env["DATAHUB_TELEMETRY_ENABLED"] = "false"
    params = StdioServerParameters(command="uvx", args=["mcp-server-datahub"], env=env)

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.list_tools()
        print(f"mutation_enabled={env.get('TOOLS_IS_MUTATION_ENABLED', 'unset')}")
        print(f"tool_count={len(result.tools)}")
        for tool in result.tools:
            print(f"- {tool.name}")


if __name__ == "__main__":
    asyncio.run(main())
