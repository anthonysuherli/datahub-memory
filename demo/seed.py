"""Seed the demo catalog: 4-dataset revenue chain with lineage + one seeded incident."""
from datahub.emitter.mce_builder import make_dataset_urn
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    DatasetPropertiesClass, SchemaMetadataClass, SchemaFieldClass,
    SchemaFieldDataTypeClass, StringTypeClass, NumberTypeClass,
    UpstreamClass, UpstreamLineageClass, OtherSchemaClass,
    InstitutionalMemoryClass, InstitutionalMemoryMetadataClass, AuditStampClass,
)
import os

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


if __name__ == "__main__":
    main()
