import re

from datahub_memory import bridge


def test_snapshot_hash_deterministic_and_sensitive():
    fields = [{"fieldPath": "a", "nativeDataType": "string"}]
    h1 = bridge.snapshot_hash(fields, ["urn:li:dataset:x"])
    assert h1 == bridge.snapshot_hash(fields, ["urn:li:dataset:x"])
    assert h1 != bridge.snapshot_hash(fields + [{"fieldPath": "b", "nativeDataType": "number"}],
                                      ["urn:li:dataset:x"])


def test_build_finding_carries_grounding():
    f = bridge.build_finding(
        "can I trust monthly_revenue?", "Yes with caveat: Jul 24 backfill incident.",
        "Investigation", [{"urn": "urn:li:dataset:x", "snapshot_hash": "abc", "ui_url": "http://u"}])
    assert f.content["grounded_in"][0]["urn"] == "urn:li:dataset:x"
    assert f.provenance[0]["url"] == "http://u"


def test_persist_then_recall_roundtrip(local_delapan):
    f = bridge.build_finding(
        "can I trust monthly_revenue?", "Yes with caveat: Jul 24 backfill incident.",
        "Investigation", [{"urn": "urn:li:dataset:x", "snapshot_hash": "abc", "ui_url": "http://u"}])
    out = bridge.persist("dh-demo", "main", [f])
    assert out["ops"][0]["op"] in ("ADD", "UPDATE", "NOOP", "SUPERSEDE")
    got = bridge.recall("dh-demo", "main", "monthly_revenue trust")
    assert got["coverage"] in ("rich", "sparse", "gap")
    assert "<preamble>" in got["preamble"]


def test_check_drift_flags_changed_hash():
    content = {"grounded_in": [{"urn": "u1", "snapshot_hash": "old"},
                               {"urn": "u2", "snapshot_hash": "same"}]}
    assert bridge.check_drift(content, {"u1": "NEW", "u2": "same"}) == ["u1"]


def test_persist_resolves_duplicate_at_write_time(local_delapan, monkeypatch):
    """memory.enabled=True: a second write of the same finding must be resolved
    (NOOP/UPDATE) against the existing row, not appended as a second ADD."""
    import delapan.core.memory.resolver as resolver_mod
    from delapan.core.config import get_config
    from delapan.core.memory.models import (
        ResolutionBatch,
        ResolutionDecision,
        ResolutionOp,
    )
    from delapan.mcp.tenancy import resolve_tenant
    from delapan.store import get_store

    async def fake_structured_completion(*, model, response_format, system, user,
                                          temperature=0.0, fallback_model=None,
                                          use_json_schema=True, max_tokens=None,
                                          reasoning_effort=None):
        # Identical candidate text -> identical fake embedding -> the resolver's
        # neighbor search matches the first write's row; pull its id out of the
        # prompt (formatted "id=<fid> sim=... title=...") and call it a NOOP.
        m = re.search(r"id=(\S+)", user)
        target_id = m.group(1) if m else None
        return ResolutionBatch(decisions=[
            ResolutionDecision(candidate_index=0, op=ResolutionOp.NOOP,
                                target_finding_id=target_id, reason="mocked: same claim")
        ])

    monkeypatch.setattr(resolver_mod, "structured_completion", fake_structured_completion)
    monkeypatch.setenv("DLP_MEMORY__ENABLED", "true")
    get_config.cache_clear()
    try:
        f1 = bridge.build_finding(
            "can I trust monthly_revenue?", "Yes with caveat: Jul 24 backfill incident.",
            "Investigation", [{"urn": "urn:li:dataset:x", "snapshot_hash": "abc", "ui_url": "http://u"}])
        first = bridge.persist("dh-demo", "resolution", [f1])
        assert first["ops"][0]["op"] == "ADD"

        f2 = bridge.build_finding(
            "can I trust monthly_revenue?", "Yes with caveat: Jul 24 backfill incident.",
            "Investigation", [{"urn": "urn:li:dataset:x", "snapshot_hash": "abc", "ui_url": "http://u"}])
        second = bridge.persist("dh-demo", "resolution", [f2])
        assert second["ops"][0]["op"] != "ADD"
        assert second["ops"][0]["op"] in ("NOOP", "UPDATE")

        ctx = resolve_tenant("dh-demo", "resolution", create=True)
        store = get_store()
        assert store.count_findings(ctx.kb_id) == 1
    finally:
        get_config.cache_clear()
