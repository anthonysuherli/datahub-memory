"""Emit a schema drift on stg_payments: amount_usd -> amount.

Run from repo root: python -m demo.drift
"""
import os

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter

from demo.seed import FIELDS, URNS, _schema


def main():
    FIELDS["stg_payments"] = [
        ("payment_id", "string"), ("amount", "number"), ("paid_date", "string")]
    emitter = DatahubRestEmitter(
        gms_server=os.environ["DATAHUB_GMS_URL"],
        token=os.environ.get("DATAHUB_GMS_TOKEN"))
    emitter.emit(MetadataChangeProposalWrapper(
        entityUrn=URNS["stg_payments"], aspect=_schema("stg_payments")))
    print("drift emitted")


if __name__ == "__main__":
    main()
