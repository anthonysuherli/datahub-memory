"""Memory bridge: DataHub-grounded findings in/out of delapan's local tier."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
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


_FINDING_RE = re.compile(
    r'<finding id="(?P<id>[^"]*)"[^>]*>.*?<content>(?P<content>.*?)</content>', re.DOTALL
)
_GROUNDED_JSON_RE = re.compile(r"\*\*Grounded In\*\*:\s*```json\s*(\[.*?\])\s*```", re.DOTALL)


def _unescape_xml(s: str) -> str:
    # render_preamble's escape() only touches &, <, > (not "); mirror that.
    return s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def _grounded_from_content(content: str) -> list[dict]:
    """Pull {urn, snapshot_hash} pairs out of a finding's rendered content
    string -- delapan's render_content (core/exploration/render.py) puts a
    "**Grounded In**:\\n```json\\n[...]```" block in each finding's content
    built by bridge.build_finding."""
    block_match = _GROUNDED_JSON_RE.search(content)
    if not block_match:
        return []
    try:
        entries = json.loads(block_match.group(1))
    except json.JSONDecodeError:
        return []  # truncated mid-JSON (budget cutoff) -- skip, don't crash recall
    return [{"urn": e["urn"], "snapshot_hash": e["snapshot_hash"]}
            for e in entries if e.get("urn") and e.get("snapshot_hash")]


def _extract_grounded(xml: str, *, kb_id: str | None = None, store=None) -> list[dict]:
    """Pull {urn, snapshot_hash} pairs for every finding the agent actually saw
    in its rendered preamble. The preamble text only tells us *which* findings
    were shown (via their `id="..."` attribute) -- delapan's _render_finding
    truncates each finding's own content to 1200 chars before it reaches the
    agent, so a finding with a long conclusion + several grounded entries can
    lose trailing entries if we parsed the preamble's copy of the content.

    To stay complete we re-fetch each visible finding's FULL row from the
    store (`store.get_finding(kb_id, finding_id)`) and parse `grounded_in` out
    of its untruncated `content`, falling back to the (possibly truncated)
    preamble copy only when the row can't be fetched (e.g. no store/kb_id
    given, or the id doesn't resolve) so recall never crashes. Restricting the
    loop to ids that appear in the preamble -- rather than re-deriving grounded
    URNs from an independent match_findings query -- preserves the honesty
    property: this can never surface a URN from a finding the agent didn't
    see."""
    grounded: dict[str, dict] = {}
    for m in _FINDING_RE.finditer(xml):
        finding_id = m.group("id")
        full_content = None
        if store is not None and kb_id is not None and finding_id:
            try:
                row = store.get_finding(kb_id, finding_id)
            except Exception:  # noqa: BLE001 — fall back to the preamble copy, don't crash recall
                row = None
            if row is not None:
                full_content = row.get("content")
        if isinstance(full_content, str):
            entries = _grounded_from_content(full_content)
        else:
            entries = _grounded_from_content(_unescape_xml(m.group("content")))
        for entry in entries:
            grounded[entry["urn"]] = entry
    return list(grounded.values())


def recall(project: str, kb: str, query: str) -> dict:
    ctx = resolve_tenant(project, kb, create=True)
    store = get_store()
    xml, coverage = asyncio.run(select_preamble(query, store=store, kb_id=ctx.kb_id))
    grounded = _extract_grounded(xml, kb_id=ctx.kb_id, store=store)
    return {"coverage": coverage, "preamble": xml, "grounded": grounded}


def check_drift(content: dict, current: dict[str, str]) -> list[str]:
    return [g["urn"] for g in content.get("grounded_in", [])
            if g["urn"] in current and current[g["urn"]] != g["snapshot_hash"]]
