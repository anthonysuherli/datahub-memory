"""Write distilled knowledge back to DataHub. Transport: emitter (OSS-safe).

Per docs/R1-decision.md, the agent's primary write-back transport is DataHub's
own MCP mutation tools (update_description, save_document, add_terms/add_tags —
all live on OSS >=1.4.0 with TOOLS_IS_MUTATION_ENABLED=true). This module is the
tested emitter fallback: used when scripting outside the agent (e.g. demo/
seeding) or if a judge's environment can't run the MCP server. Glossary-term
proposals are not implemented here — that's an MCP-only surface per R1's
"Decision for Task 5" (add_terms/add_tags), not something this module covers.

Both DatasetProperties and InstitutionalMemory are single-valued aspects: a
wholesale emit REPLACES the aspect, so both functions do read-modify-write via
DataHubGraph.get_aspect before emitting, to avoid clobbering fields/elements set
by other writers (verified live against fct_revenue: emitting
DatasetPropertiesClass(description=...) without `name` set the dataset's `name`
field to None).

Both functions degrade instead of raising: any exception (e.g. GMS unreachable)
is caught and returned as {"ok": False, "transport": "emitter", "detail": ...}
so a caller (the Task-6 agent loop) never crashes on a write-back failure — it
reads `detail` for what went wrong. No retry, no logging framework.
"""
from __future__ import annotations

import os
import time

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.ingestion.graph.client import DataHubGraph
from datahub.ingestion.graph.config import DatahubClientConfig
from datahub.metadata.schema_classes import (
    AuditStampClass,
    DatasetPropertiesClass,
    InstitutionalMemoryClass,
    InstitutionalMemoryMetadataClass,
)


def _emitter() -> DatahubRestEmitter:
    return DatahubRestEmitter(gms_server=os.environ["DATAHUB_GMS_URL"],
                              token=os.environ.get("DATAHUB_GMS_TOKEN"))


def _graph() -> DataHubGraph:
    return DataHubGraph(DatahubClientConfig(
        server=os.environ["DATAHUB_GMS_URL"],
        token=os.environ.get("DATAHUB_GMS_TOKEN")))


def fill_description(urn: str, description: str) -> dict:
    try:
        current = _graph().get_aspect(urn, DatasetPropertiesClass)
        props = current if current is not None else DatasetPropertiesClass()
        props.description = description
        _emitter().emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=props))
        return {"ok": True, "transport": "emitter", "detail": f"description set on {urn}"}
    except Exception as exc:  # noqa: BLE001 — degrade, don't crash the Task-6 agent loop
        return {"ok": False, "transport": "emitter", "detail": f"{type(exc).__name__}: {exc}"}


def write_report(urn: str, title: str, markdown: str) -> dict:
    try:
        stamp = AuditStampClass(time=int(time.time() * 1000),
                                actor="urn:li:corpuser:datahub-memory")
        new_element = InstitutionalMemoryMetadataClass(
            url="https://github.com/anthonysuherli/dh8#report",
            description=f"{title} — {markdown[:900]}", createStamp=stamp)
        current = _graph().get_aspect(urn, InstitutionalMemoryClass)
        existing = list(current.elements) if current is not None else []
        _emitter().emit(MetadataChangeProposalWrapper(
            entityUrn=urn, aspect=InstitutionalMemoryClass(elements=existing + [new_element])))
        return {"ok": True, "transport": "emitter", "detail": f"report attached to {urn}"}
    except Exception as exc:  # noqa: BLE001 — degrade, don't crash the Task-6 agent loop
        return {"ok": False, "transport": "emitter", "detail": f"{type(exc).__name__}: {exc}"}
