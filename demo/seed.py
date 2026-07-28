"""Seed the demo catalog: 4-dataset revenue chain with lineage + one seeded incident.

The incident is published TWICE, over two different surfaces, because
mcp-server-datahub v0.6.0 exposes no read tool for the institutionalMemory
aspect -- an agent driven only by that MCP server can never see it:
  1. InstitutionalMemoryClass on raw_payments (kept for parity with the UI's
     "Documentation" panel and any future institutionalMemory read tool).
  2. A DataHub Document (save_document), which IS discoverable via the MCP
     search_documents/grep_documents tools. This is the one the agent can
     actually find.

Re-seeding idempotency: before creating the document, we search_documents for
one with the exact same title and, if found, upsert that URN instead of
creating a new one. That search itself depends on the MCP document-tools
surface being available (mcp-server-datahub hides search_documents/
grep_documents while the Document catalog is empty -- see docs/R1-decision.md)
and on GraphQL keyword search finding an exact title match; if the search
fails or turns up nothing for any other reason, we fall back to creating a
new document, which WILL duplicate on repeated `python -m demo.seed` runs.
"""
# Run from repo root: python -m demo.seed
import asyncio
import json
import os

from datahub.emitter.mce_builder import make_dataset_urn
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    AuditStampClass,
    DatasetPropertiesClass,
    InstitutionalMemoryClass,
    InstitutionalMemoryMetadataClass,
    NumberTypeClass,
    OtherSchemaClass,
    SchemaFieldClass,
    SchemaFieldDataTypeClass,
    SchemaMetadataClass,
    StringTypeClass,
    UpstreamClass,
    UpstreamLineageClass,
)
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CHAIN = ["raw_payments", "stg_payments", "fct_revenue", "monthly_revenue"]
URNS = {n: make_dataset_urn("demo", n, "PROD") for n in CHAIN}

FIELDS = {
    "raw_payments": [("payment_id", "string"), ("amount_cents", "number"), ("paid_at", "string")],
    "stg_payments": [("payment_id", "string"), ("amount_usd", "number"), ("paid_date", "string")],
    "fct_revenue": [("day", "string"), ("revenue_usd", "number")],
    "monthly_revenue": [("month", "string"), ("revenue_usd", "number")],
}
DESCRIPTIONS = {
    "raw_payments": "Raw Stripe payment events, landed hourly.",
    "stg_payments": "",  # seeded gap: the agent write-back fills this
    "fct_revenue": "Daily revenue fact table.",
    "monthly_revenue": "Monthly revenue rollup used by the board dashboard.",
}


INCIDENT_TITLE = "INCIDENT 2026-07-24: Stripe webhook outage — late backfill"
INCIDENT_BODY = """## Incident

Stripe webhook delivery was down for ~6 hours on 2026-07-24. Payment events
landed late in `raw_payments`, so every downstream table in the revenue
chain -- `stg_payments`, `fct_revenue`, and `monthly_revenue` -- carried an
incomplete Jul 24 slice until the backfill completed.

## Resolution

The missed events were backfilled and `stg_payments` -> `fct_revenue` ->
`monthly_revenue` were recomputed on 2026-07-26. Jul 24 figures are now
correct; treat any export of that date taken before 2026-07-26 as stale.
"""


def _schema(name):
    fields = [
        SchemaFieldClass(
            fieldPath=f, nativeDataType=t,
            type=SchemaFieldDataTypeClass(
                type=NumberTypeClass() if t == "number" else StringTypeClass()),
        )
        for f, t in FIELDS[name]
    ]
    return SchemaMetadataClass(
        schemaName=name, platform="urn:li:dataPlatform:demo", version=0,
        hash="", platformSchema=OtherSchemaClass(rawSchema=""), fields=fields,
    )


def _tool_text(result) -> str:
    for block in getattr(result, "content", None) or []:
        if hasattr(block, "text"):
            return block.text
    return ""


async def _publish_incident_document() -> None:
    """Publish the seeded incident as a DataHub Document -- see module
    docstring for why this is needed and what "idempotent-enough" means here.
    Reuses the mcp-server-datahub stdio call pattern from
    demo/probe_save_document.py.
    """
    env = dict(os.environ)
    env["TOOLS_IS_MUTATION_ENABLED"] = "true"
    env["DATAHUB_TELEMETRY_ENABLED"] = "false"
    params = StdioServerParameters(command="uvx", args=["mcp-server-datahub"], env=env)

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        existing_urn = None
        try:
            search = await session.call_tool(
                "search_documents", {"query": f'/q "{INCIDENT_TITLE}"'})
            data = json.loads(_tool_text(search) or "{}")
            for r in data.get("searchResults", []):
                title = (r.get("entity") or {}).get("info", {}).get("title")
                if title == INCIDENT_TITLE:
                    existing_urn = r["entity"]["urn"]
                    break
        except Exception as exc:  # noqa: BLE001 — degrade to create-new (may duplicate)
            print(f"  (search_documents unavailable/failed: {exc}; creating new doc)")

        args = {
            "document_type": "Note",
            "title": INCIDENT_TITLE,
            "content": INCIDENT_BODY,
            "related_assets": [URNS["raw_payments"]],
        }
        if existing_urn:
            args["urn"] = existing_urn
        result = await session.call_tool("save_document", args)
        print("incident document:", _tool_text(result))


def main():
    emitter = DatahubRestEmitter(
        gms_server=os.environ["DATAHUB_GMS_URL"],
        token=os.environ.get("DATAHUB_GMS_TOKEN"),
    )
    for name in CHAIN:
        urn = URNS[name]
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=urn,
            aspect=DatasetPropertiesClass(name=name, description=DESCRIPTIONS[name])))
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=_schema(name)))
    for down, up in zip(CHAIN[1:], CHAIN[:-1]):
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=URNS[down],
            aspect=UpstreamLineageClass(
                upstreams=[UpstreamClass(dataset=URNS[up], type="TRANSFORMED")])))
    # the seeded incident the investigation should find
    stamp = AuditStampClass(time=0, actor="urn:li:corpuser:datahub")
    emitter.emit(MetadataChangeProposalWrapper(
        entityUrn=URNS["raw_payments"],
        aspect=InstitutionalMemoryClass(elements=[InstitutionalMemoryMetadataClass(
            url="https://example.com/incidents/2026-07-24-stripe-backfill",
            description="INCIDENT 2026-07-24: Stripe webhook outage; 6h of events "
                        "backfilled late. Downstream daily numbers for Jul 24 corrected Jul 26.",
            createStamp=stamp)])))
    print("seeded", list(URNS.values()))
    # Agent-discoverable copy of the same incident (see module docstring):
    # mcp-server-datahub v0.6.0 has no institutionalMemory read tool.
    asyncio.run(_publish_incident_document())


if __name__ == "__main__":
    main()
