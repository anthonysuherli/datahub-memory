from unittest.mock import MagicMock, patch

from datahub.metadata.schema_classes import (
    AuditStampClass,
    DatasetPropertiesClass,
    InstitutionalMemoryClass,
    InstitutionalMemoryMetadataClass,
)

from datahub_memory import writeback


@patch("datahub_memory.writeback._graph")
@patch("datahub_memory.writeback._emitter")
def test_fill_description_preserves_name(mock_em, mock_graph):
    em = MagicMock()
    mock_em.return_value = em
    graph = MagicMock()
    graph.get_aspect.return_value = DatasetPropertiesClass(
        name="stg_payments", description="", customProperties={"owner_team": "payments"}
    )
    mock_graph.return_value = graph

    out = writeback.fill_description("urn:li:dataset:x", "Staged payments, USD-normalized.")

    assert out["ok"] and out["transport"] == "emitter"
    aspect = em.emit.call_args[0][0].aspect
    assert aspect.description == "Staged payments, USD-normalized."
    assert aspect.name == "stg_payments"  # read-modify-write must not clobber name
    assert aspect.customProperties == {"owner_team": "payments"}  # nor customProperties


@patch("datahub_memory.writeback._graph")
@patch("datahub_memory.writeback._emitter")
def test_fill_description_handles_missing_aspect(mock_em, mock_graph):
    em = MagicMock()
    mock_em.return_value = em
    graph = MagicMock()
    graph.get_aspect.return_value = None
    mock_graph.return_value = graph

    out = writeback.fill_description("urn:li:dataset:x", "Staged payments, USD-normalized.")

    assert out["ok"] and out["transport"] == "emitter"
    aspect = em.emit.call_args[0][0].aspect
    assert aspect.description == "Staged payments, USD-normalized."


@patch("datahub_memory.writeback._graph")
@patch("datahub_memory.writeback._emitter")
def test_write_report_appends_institutional_memory(mock_em, mock_graph):
    em = MagicMock()
    mock_em.return_value = em
    existing = InstitutionalMemoryMetadataClass(
        url="https://example.com/incidents/2026-07-24-stripe-backfill",
        description="INCIDENT 2026-07-24: Stripe webhook outage.",
        createStamp=AuditStampClass(time=0, actor="urn:li:corpuser:datahub"),
    )
    graph = MagicMock()
    graph.get_aspect.return_value = InstitutionalMemoryClass(elements=[existing])
    mock_graph.return_value = graph

    out = writeback.write_report(
        "urn:li:dataset:x", "Trust check: monthly_revenue", "## Verdict\nTrusted with caveat."
    )

    assert out["ok"]
    aspect = em.emit.call_args[0][0].aspect
    assert len(aspect.elements) == 2
    assert aspect.elements[0] is existing  # seeded incident element survives
    assert "Trust check" in aspect.elements[-1].description


@patch("datahub_memory.writeback._graph")
@patch("datahub_memory.writeback._emitter")
def test_write_report_handles_missing_aspect(mock_em, mock_graph):
    em = MagicMock()
    mock_em.return_value = em
    graph = MagicMock()
    graph.get_aspect.return_value = None
    mock_graph.return_value = graph

    out = writeback.write_report(
        "urn:li:dataset:x", "Trust check: monthly_revenue", "## Verdict\nTrusted with caveat."
    )

    assert out["ok"]
    aspect = em.emit.call_args[0][0].aspect
    assert len(aspect.elements) == 1
    assert "Trust check" in aspect.elements[-1].description


@patch("datahub_memory.writeback._graph")
def test_fill_description_degrades_on_connection_error(mock_graph):
    mock_graph.side_effect = ConnectionError("GMS unreachable")

    out = writeback.fill_description("urn:li:dataset:x", "Staged payments, USD-normalized.")

    assert out == {
        "ok": False,
        "transport": "emitter",
        "detail": "ConnectionError: GMS unreachable",
    }


@patch("datahub_memory.writeback._graph")
def test_write_report_degrades_on_connection_error(mock_graph):
    mock_graph.side_effect = ConnectionError("GMS unreachable")

    out = writeback.write_report(
        "urn:li:dataset:x", "Trust check: monthly_revenue", "## Verdict\nTrusted with caveat."
    )

    assert out == {
        "ok": False,
        "transport": "emitter",
        "detail": "ConnectionError: GMS unreachable",
    }
