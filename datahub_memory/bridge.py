"""Memory bridge: DataHub-grounded findings in/out of delapan's local tier."""
from __future__ import annotations

import asyncio
import hashlib
import json
from uuid import uuid4

from delapan.core.agent.preamble import select_preamble
from delapan.core.config import get_config
from delapan.core.exploration.models import Finding
from delapan.core.memory.persist import resolve_and_persist
from delapan.mcp.tenancy import resolve_tenant
from delapan.store import get_store


def snapshot_hash(schema_fields: list[dict], upstream_urns: list[str]) -> str:
    payload = json.dumps(
        {"fields": [(f.get("fieldPath"), f.get("nativeDataType")) for f in schema_fields],
         "upstreams": sorted(upstream_urns)},
        sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_finding(question: str, conclusion: str, category: str,
                  grounded: list[dict]) -> Finding:
    return Finding(
        exploration_id=uuid4().hex,
        project_id="",  # filled by persist via tenant ctx; row builder uses ctx ids
        category=category,
        title=question[:200],
        content={"question": question, "conclusion": conclusion,
                 "grounded_in": grounded},
        confidence=0.9,
        tags=["datahub-memory"],
        provenance=[{"url": g["ui_url"], "note": g["urn"]} for g in grounded if g.get("ui_url")],
    )


def persist(project: str, kb: str, findings: list[Finding]) -> dict:
    ctx = resolve_tenant(project, kb, create=True)
    store = get_store()
    cfg = get_config()
    outcome = asyncio.run(resolve_and_persist(ctx, store, findings, cfg))
    if outcome.events:
        ops = [{"op": e.op, "title": e.candidate_title, "reason": e.reason}
               for e in outcome.events]
    else:
        # cfg.memory.enabled=False (delapan's shipped default) takes the
        # kill-switch path in resolve_and_persist: pure ADD, no resolver call,
        # no event log — affected_finding_ids is populated but events is not.
        # Synthesize ADD ops 1:1 with the candidates (insert_findings preserves
        # submission order) so callers get a uniform {op,title,reason} shape
        # regardless of whether write-time resolution is enabled.
        ops = [{"op": "ADD", "title": f.title, "reason": ""} for f in findings]
    return {"ops": ops, "affected_ids": list(outcome.affected_finding_ids)}


def recall(project: str, kb: str, query: str) -> dict:
    ctx = resolve_tenant(project, kb, create=True)
    store = get_store()
    xml, coverage = asyncio.run(select_preamble(query, store=store, kb_id=ctx.kb_id))
    return {"coverage": coverage, "preamble": xml}


def check_drift(content: dict, current: dict[str, str]) -> list[str]:
    return [g["urn"] for g in content.get("grounded_in", [])
            if g["urn"] in current and current[g["urn"]] != g["snapshot_hash"]]
