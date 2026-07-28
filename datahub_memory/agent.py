"""One agent, two tool surfaces: DataHub MCP (stdio) + in-process memory tools."""
from __future__ import annotations

import asyncio
import concurrent.futures
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
from datahub.metadata.schema_classes import SchemaMetadataClass, UpstreamLineageClass

from datahub_memory import bridge, writeback
from datahub_memory.prompts import SYSTEM

# Pinned rather than left to the CLI/user default: this SDK subprocess would
# otherwise inherit whatever model the invoking machine's ~/.claude/settings.json
# prefers (observed: an opus[1m] alias, ~10-20x the cost of a pinned sonnet for
# this workload) even with setting_sources=[] below, since that preference is
# not one of the three filesystem sources setting_sources gates.
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-4-5")

# Review finding Important-4: bridge.recall/persist each call asyncio.run()
# internally (see bridge.py), and each is dispatched here via asyncio.to_thread
# — i.e. onto whatever thread the default executor hands out, which can differ
# call to call. delapan's embedding/gateway clients (delapan/core/clients/
# embeddings.py:_client, delapan/core/clients/ai_gateway.py:gateway_client)
# cache one AsyncOpenAI client at module scope, bound to the event loop that
# was running when it was first constructed. A fresh asyncio.run() on a
# *different* thread reusing that stale-loop client risks "attached to a
# different loop" errors from the underlying httpx/asyncio transport. Routing
# every bridge call through a single-worker executor serializes them onto one
# thread, and resetting the cached clients before each call forces a fresh
# client bound to that thread's fresh loop.
_BRIDGE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def _reset_delapan_clients() -> None:
    """Drop delapan's cached LLM/embedding clients so the next asyncio.run()
    (on this executor's single worker thread) builds fresh ones instead of
    reusing a client bound to a stale event loop. See _BRIDGE_EXECUTOR above."""
    import delapan.core.clients.embeddings as _emb
    _emb._client = None
    try:
        import delapan.core.clients.ai_gateway as _gw
        _gw.gateway_client.cache_clear()  # lru_cache(maxsize=1), not a bare global
    except ImportError:
        pass


def _run_recall(project: str, kb: str, query_text: str) -> dict:
    _reset_delapan_clients()
    return bridge.recall(project, kb, query_text)


def _run_persist(project: str, kb: str, findings: list) -> dict:
    _reset_delapan_clients()
    return bridge.persist(project, kb, findings)


def route(coverage: str) -> str:
    # Amendment (user-ratified 2026-07-28): "answer_from_memory" now covers
    # both "rich" and "sparse" coverage -- only "gap" (nothing relevant
    # banded at all) forces a real investigation. A memory-first product
    # answers from what it knows and verifies freshness on demand, rather
    # than re-deriving everything from scratch at partial coverage. See
    # prompts.py step 2 for the bounded freshness-check mechanism this
    # relies on.
    return "investigate" if coverage == "gap" else "answer_from_memory"


@tool("memory_recall", "Tap the KB for prior grounded knowledge about a question",
      {"project": str, "kb": str, "query": str})
async def memory_recall(args):
    # bridge.recall is sync but spins its own asyncio.run() internally; called
    # directly from this already-running (SDK) event loop that raises
    # "asyncio.run() cannot be called from a running event loop". Dispatch to
    # the single-worker bridge executor (see _BRIDGE_EXECUTOR) rather than the
    # default thread pool so concurrent bridge calls can't land on different
    # threads and race delapan's cached-client hazard.
    loop = asyncio.get_running_loop()
    out = await loop.run_in_executor(
        _BRIDGE_EXECUTOR, _run_recall, args["project"], args["kb"], args["query"])
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
    loop = asyncio.get_running_loop()
    out = await loop.run_in_executor(
        _BRIDGE_EXECUTOR, _run_persist, args["project"], args["kb"], [f])
    return {"content": [{"type": "text", "text": json.dumps(out)}]}


def _current_fields(urn: str) -> list[dict]:
    """CURRENT schema fields for urn, in the exact {fieldPath, nativeDataType}
    shape and alphabetical-by-fieldPath order the datahub MCP server's
    get_entities/list_schema_fields tools hand the agent -- verified live
    against a real persisted finding's stored snapshot_hash (task-7 report,
    Fix report 2) before this was written, since bridge.snapshot_hash hashes
    the fields list in the order given, not sorted."""
    aspect = writeback._graph().get_aspect(urn, SchemaMetadataClass)
    fields = aspect.fields if aspect is not None else []
    return sorted(
        ({"fieldPath": f.fieldPath, "nativeDataType": f.nativeDataType} for f in fields),
        key=lambda d: d["fieldPath"],
    )


def _direct_upstreams(urn: str) -> list[str]:
    aspect = writeback._graph().get_aspect(urn, UpstreamLineageClass)
    if aspect is None:
        return []
    return [u.dataset for u in aspect.upstreams]


def _transitive_upstreams(urn: str) -> list[str]:
    seen: set[str] = set()
    frontier = [urn]
    while frontier:
        for up in _direct_upstreams(frontier.pop()):
            if up not in seen:
                seen.add(up)
                frontier.append(up)
    return sorted(seen)


def _is_fresh(urn: str, stored_hash: str) -> bool:
    """True if urn's CURRENT schema+lineage still hashes to stored_hash.

    memory_persist's `upstream_urns` comes straight from whatever the agent
    passed after its OWN get_lineage call, and that has been observed live
    to vary run-to-run between "direct upstream only" and "full transitive
    closure to the lineage root" -- both conventions were confirmed against
    real stored snapshot_hash values (see task-7 report, Fix report 2), and
    there's no way to know in advance which one a given finding used. Rather
    than guess, accept a match under EITHER convention: a real schema/lineage
    change breaks the hash under both, so this can't paper over an actual
    drift -- it only avoids a false "changed" caused by upstream-depth
    reporting variance that isn't a drift at all.
    """
    fields = _current_fields(urn)
    direct, transitive = _direct_upstreams(urn), _transitive_upstreams(urn)
    candidates = {bridge.snapshot_hash(fields, direct), bridge.snapshot_hash(fields, transitive)}
    return stored_hash in candidates


@tool("check_freshness",
      "Deterministically check whether grounded DataHub entities have drifted "
      "since a finding was persisted: recompute each URN's snapshot_hash from "
      "its CURRENT schema fields + lineage and compare to the recorded hash. "
      "No model judgment involved -- use this instead of guessing from memory.",
      {"grounded": list})
async def check_freshness(args):
    grounded = args["grounded"]
    changed = [
        g["urn"] for g in grounded
        if not await asyncio.to_thread(_is_fresh, g["urn"], g["snapshot_hash"])
    ]
    out = {"changed": changed, "checked": len(grounded)}
    return {"content": [{"type": "text", "text": json.dumps(out)}]}


@tool("writeback_description",
      "Fallback only: fill an empty/stale dataset description in DataHub. Use this "
      "only if the DataHub MCP server's own update_description tool call failed.",
      {"urn": str, "description": str})
async def writeback_description(args):
    # writeback.fill_description does blocking HTTP (DataHubGraph/rest emitter);
    # keep it off the SDK's event loop like the bridge call sites above.
    out = await asyncio.to_thread(writeback.fill_description, **args)
    return {"content": [{"type": "text", "text": json.dumps(out)}]}


@tool("writeback_report",
      "Fallback only: attach the investigation report to a DataHub entity. Use "
      "this only if the DataHub MCP server's own save_document tool call failed.",
      {"urn": str, "title": str, "markdown": str})
async def writeback_report(args):
    # Same rationale as writeback_description: blocking HTTP off the event loop.
    out = await asyncio.to_thread(writeback.write_report, **args)
    return {"content": [{"type": "text", "text": json.dumps(out)}]}


MEMORY_SERVER = create_sdk_mcp_server(
    name="memory", version="0.1.0",
    tools=[memory_recall, memory_persist, check_freshness,
           writeback_description, writeback_report])


async def run_question(question: str, project: str = "dh-demo", kb: str = "main") -> dict:
    # Minor-b: a bare KeyError here ("DATAHUB_GMS_URL") reads as a crash, not a
    # setup problem. Fail with a message that names the fix.
    if "DATAHUB_GMS_URL" not in os.environ:
        raise SystemExit(
            "DATAHUB_GMS_URL is not set. Source .env.local (see demo/quickstart.sh) "
            "before running the agent."
        )

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
    # Minor-a: manual fallback so a degrade path (exception before any
    # ResultMessage, or an SDK version that omits num_turns) doesn't report
    # turns=0 next to a nonzero tool_calls count. One AssistantMessage ~= one
    # agent turn; used only when the SDK's own turns count never arrives.
    manual_turns = 0
    is_error = False
    stop_reason: str | None = None
    try:
        async for message in query(prompt=f"{question}\n(project={project}, kb={kb})",
                                    options=options):
            if isinstance(message, AssistantMessage):
                manual_turns += 1
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
                # Important-2: run_question used to return a success-shaped
                # dict even when every tool call failed. Surface the SDK's own
                # verdict instead of silently swallowing it.
                is_error = message.is_error
                stop_reason = message.stop_reason or message.subtype
                if message.permission_denials:
                    denials = f"{len(message.permission_denials)} permission denial(s)"
                    stop_reason = f"{stop_reason}: {denials}" if stop_reason else denials
    except Exception as exc:  # noqa: BLE001 — the CLI raises a bare Exception
        # (not a ResultMessage) when max_turns is exhausted before the agent
        # concludes; degrade to whatever was accumulated instead of crashing
        # the caller, which would otherwise lose the partial investigation.
        if not answer:
            answer = f"(stopped: {exc})"
        if not duration_s:
            duration_s = round(time.time() - t0, 1)
        is_error = True
        stop_reason = str(exc)

    if not turns:
        turns = manual_turns

    return {"answer": answer, "mode": "agent",
            "is_error": is_error, "stop_reason": stop_reason,
            "counters": {"turns": turns, "tool_calls": tool_calls,
                         "duration_s": duration_s}}
