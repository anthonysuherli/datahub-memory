"""Hermetic check of the stdio stub's tool registry: no subprocess, no
network -- just the in-process FastMCP tool manager's registered names."""
from datahub_memory import mcp_stub


def test_registers_the_five_expected_tools():
    names = {t.name for t in mcp_stub.mcp._tool_manager.list_tools()}
    assert names == {
        "memory_recall",
        "memory_persist",
        "check_freshness",
        "writeback_description",
        "writeback_report",
    }
