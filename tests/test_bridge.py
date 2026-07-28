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
