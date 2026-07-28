"""Verify save_document mutation tool works end-to-end on local/cloud DataHub.

Spawns `mcp-server-datahub` with TOOLS_IS_MUTATION_ENABLED=true, initializes
the MCP handshake, and calls save_document to create a test document. Prints
the tool response (isError, document URN, etc.) for manual verification against
the DataHub UI.

Usage:
    .venv/bin/python demo/probe_save_document.py

Requires DATAHUB_GMS_URL (and DATAHUB_GMS_TOKEN if auth is enabled) in the
environment -- source .env.local first.
"""

from __future__ import annotations

import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    # Ensure mutation tool is enabled; pass through all env vars to the server.
    env = dict(os.environ)
    env["TOOLS_IS_MUTATION_ENABLED"] = "true"
    env["DATAHUB_TELEMETRY_ENABLED"] = "false"

    # Check required env vars before spawning server.
    gms_url = env.get("DATAHUB_GMS_URL")
    if not gms_url:
        print("ERROR: DATAHUB_GMS_URL not set in environment")
        print("       source .env.local first, or set it manually")
        return

    params = StdioServerParameters(command="uvx", args=["mcp-server-datahub"], env=env)

    print(f"Spawning mcp-server-datahub with TOOLS_IS_MUTATION_ENABLED=true")
    print(f"GMS URL: {gms_url}")
    print()

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Call save_document with test data.
            print("Calling save_document...")
            result = await session.call_tool(
                "save_document",
                {
                    "title": "R1 verification doc",
                    "content": "Created by datahub-memory Task 2 R1 verification script.",
                    "document_type": "Note",
                },
            )

            # Print the response.
            print()
            print("Response:")
            if hasattr(result, "content") and result.content:
                for content_block in result.content:
                    if hasattr(content_block, "text"):
                        print(content_block.text)
                    else:
                        print(json.dumps(content_block, indent=2, default=str))
            else:
                print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
