"""Hermetic tests for run_question's message-loop bookkeeping (no live agent
run, no spend): monkeypatch claude_agent_sdk.query with a fake async
generator yielding real SDK message dataclasses directly."""
import json
from unittest.mock import MagicMock, patch

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock
from datahub.metadata.schema_classes import (
    OtherSchemaClass,
    SchemaFieldClass,
    SchemaFieldDataTypeClass,
    SchemaMetadataClass,
    StringTypeClass,
    UpstreamClass,
    UpstreamLineageClass,
)

import datahub_memory.agent as agent_mod
from datahub_memory import bridge


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


def _field(path: str, native_type: str) -> SchemaFieldClass:
    return SchemaFieldClass(
        fieldPath=path, nativeDataType=native_type,
        type=SchemaFieldDataTypeClass(type=StringTypeClass()))


def _mock_graph(schema_by_urn: dict[str, list], upstream_by_urn: dict[str, list[str]]) -> MagicMock:
    """A DataHubGraph stand-in: get_aspect(urn, cls) served from two plain
    dicts, mirroring the real read-two-aspects pattern _current_fields/
    _direct_upstreams use (see writeback._graph() callers in agent.py)."""
    graph = MagicMock()

    def get_aspect(urn, aspect_cls):
        if aspect_cls is SchemaMetadataClass:
            fields = schema_by_urn.get(urn)
            if fields is None:
                return None
            return SchemaMetadataClass(
                schemaName=urn, platform="urn:li:dataPlatform:demo", version=0,
                hash="", platformSchema=OtherSchemaClass(rawSchema=""), fields=fields)
        if aspect_cls is UpstreamLineageClass:
            ups = upstream_by_urn.get(urn)
            if not ups:
                return None
            return UpstreamLineageClass(
                upstreams=[UpstreamClass(dataset=u, type="TRANSFORMED") for u in ups])
        raise AssertionError(f"unexpected aspect class {aspect_cls}")

    graph.get_aspect.side_effect = get_aspect
    return graph


@patch("datahub_memory.writeback._graph")
async def test_check_freshness_matches_unchanged_entity(mock_graph_fn):
    """Same fields/upstream as recorded (graph returns fields OUT of
    fieldPath order, to prove _current_fields sorts them like
    list_schema_fields does) -> reports fresh, nothing changed."""
    urn = "urn:li:dataset:(urn:li:dataPlatform:demo,x,PROD)"
    up = "urn:li:dataset:(urn:li:dataPlatform:demo,up,PROD)"
    mock_graph_fn.return_value = _mock_graph(
        schema_by_urn={urn: [_field("b", "string"), _field("a", "number")]},
        upstream_by_urn={urn: [up]},
    )
    stored_hash = bridge.snapshot_hash(
        [{"fieldPath": "a", "nativeDataType": "number"},
         {"fieldPath": "b", "nativeDataType": "string"}],
        [up],
    )

    out = await agent_mod.check_freshness.handler(
        {"grounded": [{"urn": urn, "snapshot_hash": stored_hash}]})

    assert json.loads(out["content"][0]["text"]) == {"changed": [], "checked": 1}


@patch("datahub_memory.writeback._graph")
async def test_check_freshness_detects_changed_entity(mock_graph_fn):
    """Current schema no longer matches what was recorded (the drift.py
    scenario: amount_usd renamed to amount) -> reports it changed."""
    urn = "urn:li:dataset:(urn:li:dataPlatform:demo,stg_payments,PROD)"
    mock_graph_fn.return_value = _mock_graph(
        schema_by_urn={urn: [_field("amount", "number")]},  # renamed, post-drift
        upstream_by_urn={},
    )
    stale_hash = bridge.snapshot_hash([{"fieldPath": "amount_usd", "nativeDataType": "number"}], [])

    out = await agent_mod.check_freshness.handler(
        {"grounded": [{"urn": urn, "snapshot_hash": stale_hash}]})

    assert json.loads(out["content"][0]["text"]) == {"changed": [urn], "checked": 1}


@patch("datahub_memory.writeback._graph")
async def test_check_freshness_accepts_either_upstream_reporting_convention(mock_graph_fn):
    """memory_persist's upstream_urns comes from whatever the agent passed
    after its own get_lineage call, observed live to vary between direct-only
    and full-transitive-to-root (task-7 report, Fix report 2). A hash built
    from the full transitive closure must still read as fresh."""
    leaf = "urn:li:dataset:(urn:li:dataPlatform:demo,leaf,PROD)"
    mid = "urn:li:dataset:(urn:li:dataPlatform:demo,mid,PROD)"
    root = "urn:li:dataset:(urn:li:dataPlatform:demo,root,PROD)"
    mock_graph_fn.return_value = _mock_graph(
        schema_by_urn={leaf: [_field("a", "string")]},
        upstream_by_urn={leaf: [mid], mid: [root]},
    )
    stored_hash = bridge.snapshot_hash([{"fieldPath": "a", "nativeDataType": "string"}], [mid, root])

    out = await agent_mod.check_freshness.handler(
        {"grounded": [{"urn": leaf, "snapshot_hash": stored_hash}]})

    assert json.loads(out["content"][0]["text"]) == {"changed": [], "checked": 1}
