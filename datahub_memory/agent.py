"""One agent, two tool surfaces: DataHub MCP (stdio) + in-process memory tools."""
from __future__ import annotations

import json
import os
import time

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from datahub_memory import bridge, writeback
from datahub_memory.prompts import SYSTEM

# Pinned rather than left to the CLI/user default: this SDK subprocess would
# otherwise inherit whatever model the invoking machine's ~/.claude/settings.json
# prefers (observed: an opus[1m] alias, ~10-20x the cost of a pinned sonnet for
# this workload) even with setting_sources=[] below, since that preference is
# not one of the three filesystem sources setting_sources gates.
AGENT_MODEL = "claude-sonnet-4-5"


def route(coverage: str) -> str:
    return "answer_from_memory" if coverage == "rich" else "investigate"


@tool("memory_recall", "Tap the KB for prior grounded knowledge about a question",
      {"project": str, "kb": str, "query": str})
async def memory_recall(args):
    out = bridge.recall(args["project"], args["kb"], args["query"])
    out["route"] = route(out["coverage"])
    return {"content": [{"type": "text", "text": json.dumps(out)}]}


@tool("memory_persist", "Persist an investigation conclusion as a grounded finding",
      {"project": str, "kb": str, "question": str, "conclusion": str,
       "category": str, "grounded": list})
async def memory_persist(args):
    grounded = [
        {"urn": g["urn"],
         "snapshot_hash": bridge.snapshot_hash(g.get("schema_fields", []),
                                                g.get("upstream_urns", [])),
         "ui_url": g.get("ui_url", "")}
        for g in args["grounded"]
    ]
    f = bridge.build_finding(args["question"], args["conclusion"],
                              args["category"], grounded)
    out = bridge.persist(args["project"], args["kb"], [f])
    return {"content": [{"type": "text", "text": json.dumps(out)}]}


@tool("writeback_description",
      "Fallback only: fill an empty/stale dataset description in DataHub. Use this "
      "only if the DataHub MCP server's own update_description tool call failed.",
      {"urn": str, "description": str})
async def writeback_description(args):
    return {"content": [{"type": "text",
                         "text": json.dumps(writeback.fill_description(**args))}]}


@tool("writeback_report",
      "Fallback only: attach the investigation report to a DataHub entity. Use "
      "this only if the DataHub MCP server's own save_document tool call failed.",
      {"urn": str, "title": str, "markdown": str})
async def writeback_report(args):
    return {"content": [{"type": "text",
                         "text": json.dumps(writeback.write_report(**args))}]}


MEMORY_SERVER = create_sdk_mcp_server(
    name="memory", version="0.1.0",
    tools=[memory_recall, memory_persist, writeback_description, writeback_report])


async def run_question(question: str, project: str = "dh-demo", kb: str = "main") -> dict:
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM,
        mcp_servers={
            "memory": MEMORY_SERVER,
            "datahub": {
                "command": "uvx",
                "args": ["mcp-server-datahub"],
                "env": {
                    "DATAHUB_GMS_URL": os.environ["DATAHUB_GMS_URL"],
                    "DATAHUB_GMS_TOKEN": os.environ.get("DATAHUB_GMS_TOKEN", ""),
                    # Primary write path (docs/R1-decision.md): mutation tools
                    # (update_description, save_document, ...) are gated off by
                    # default and must be explicitly enabled.
                    "TOOLS_IS_MUTATION_ENABLED": "true",
                    # Without this, the server's Mixpanel telemetry ping hangs
                    # indefinitely on networks that block it (see demo/quickstart.sh).
                    "DATAHUB_TELEMETRY_ENABLED": "false",
                },
            },
        },
        allowed_tools=["mcp__memory__*", "mcp__datahub__*"],
        # This agent only ever needs the two MCP tool surfaces above; disable
        # the CLI's built-in Read/Write/Bash/etc. toolset entirely.
        tools=[],
        # SDK isolation mode: don't load this machine's ~/.claude/settings.json,
        # project .claude/settings.json, or .claude/settings.local.json. Without
        # this, an unrelated global Stop hook (observed: br8n's session-note
        # capture) fires against this project on every run.
        setting_sources=[],
        model=AGENT_MODEL,
        max_turns=25,
    )

    t0 = time.time()
    turns, tool_calls, duration_s, answer = 0, 0, 0.0, ""
    try:
        async for message in query(prompt=f"{question}\n(project={project}, kb={kb})",
                                    options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        tool_calls += 1
                    elif isinstance(block, TextBlock):
                        answer = block.text
            elif isinstance(message, ResultMessage):
                turns = message.num_turns
                duration_s = round(message.duration_ms / 1000, 1)
                if message.result:
                    answer = message.result
    except Exception as exc:  # noqa: BLE001 — the CLI raises a bare Exception
        # (not a ResultMessage) when max_turns is exhausted before the agent
        # concludes; degrade to whatever was accumulated instead of crashing
        # the caller, which would otherwise lose the partial investigation.
        if not answer:
            answer = f"(stopped: {exc})"
        if not duration_s:
            duration_s = round(time.time() - t0, 1)

    return {"answer": answer, "mode": "agent",
            "counters": {"turns": turns, "tool_calls": tool_calls,
                         "duration_s": duration_s}}
