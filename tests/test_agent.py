"""Hermetic tests for run_question's message-loop bookkeeping (no live agent
run, no spend): monkeypatch claude_agent_sdk.query with a fake async
generator yielding real SDK message dataclasses directly."""
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

import datahub_memory.agent as agent_mod


async def _fake_query_success(*, prompt, options):
    yield AssistantMessage(
        content=[
            ToolUseBlock(id="1", name="mcp__memory__memory_recall", input={}),
            TextBlock(text="Trusted with caveat."),
        ],
        model="test-model",
    )
    yield ResultMessage(
        subtype="success",
        duration_ms=1200,
        duration_api_ms=800,
        is_error=False,
        num_turns=3,
        session_id="s1",
        stop_reason=None,
        result="Grounded in: urn:li:dataset:x",
        permission_denials=None,
    )


async def _fake_query_error(*, prompt, options):
    yield AssistantMessage(
        content=[ToolUseBlock(id="1", name="mcp__datahub__search", input={})],
        model="test-model",
    )
    yield ResultMessage(
        subtype="error_max_turns",
        duration_ms=500,
        duration_api_ms=300,
        is_error=True,
        num_turns=1,
        session_id="s2",
        stop_reason="max_turns",
        result=None,
        permission_denials=[{"tool": "mcp__datahub__update_description"}],
    )


async def _fake_query_no_turns_reported(*, prompt, options):
    # ResultMessage.num_turns=0: exercises the manual-turns fallback (minor-a)
    # so a degrade-ish path doesn't report turns=0 next to nonzero tool_calls.
    yield AssistantMessage(
        content=[ToolUseBlock(id="1", name="mcp__memory__memory_recall", input={})],
        model="test-model",
    )
    yield AssistantMessage(
        content=[ToolUseBlock(id="2", name="mcp__datahub__search", input={})],
        model="test-model",
    )
    yield ResultMessage(
        subtype="success",
        duration_ms=100,
        duration_api_ms=50,
        is_error=False,
        num_turns=0,
        session_id="s3",
        result="ok",
    )


async def test_run_question_counts_turns_and_tool_calls(monkeypatch):
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://localhost:8080")
    monkeypatch.setattr(agent_mod, "query", _fake_query_success)

    out = await agent_mod.run_question("Can I trust monthly_revenue?")

    assert out["answer"] == "Grounded in: urn:li:dataset:x"
    assert out["is_error"] is False
    assert out["counters"] == {"turns": 3, "tool_calls": 1, "duration_s": 1.2}


async def test_run_question_propagates_is_error_and_stop_reason(monkeypatch):
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://localhost:8080")
    monkeypatch.setattr(agent_mod, "query", _fake_query_error)

    out = await agent_mod.run_question("Can I trust monthly_revenue?")

    assert out["is_error"] is True
    assert "max_turns" in out["stop_reason"]
    assert "1 permission denial" in out["stop_reason"]
    assert out["counters"]["tool_calls"] == 1
    assert out["counters"]["turns"] == 1


async def test_run_question_falls_back_to_manual_turns(monkeypatch):
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://localhost:8080")
    monkeypatch.setattr(agent_mod, "query", _fake_query_no_turns_reported)

    out = await agent_mod.run_question("Can I trust monthly_revenue?")

    assert out["counters"]["turns"] == 2  # manual count, since num_turns reported 0
    assert out["counters"]["tool_calls"] == 2


async def test_run_question_missing_datahub_gms_url_raises_system_exit(monkeypatch):
    monkeypatch.delenv("DATAHUB_GMS_URL", raising=False)

    try:
        await agent_mod.run_question("Can I trust monthly_revenue?")
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert ".env.local" in str(exc)
