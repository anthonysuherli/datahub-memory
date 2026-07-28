# "Data Memory" (DataHub hackathon) Implementation Plan

**Status: all 10 tasks complete** (see git history; checkboxes left unticked — the plan was executed task-by-task by subagents).

**Goal:** Build and submit `datahub-memory` — an agent that investigates data questions via DataHub's MCP server, persists conclusions as delapan findings grounded in DataHub URNs, and writes distilled knowledge back to DataHub — for the Build with DataHub hackathon (Challenge 1, deadline Aug 10 2026 5pm EDT).

**Architecture:** New standalone repo. One Claude Agent SDK loop wired to two tool surfaces: DataHub's `mcp-server-datahub` (stdio) for catalog reads/writes, and an in-process SDK MCP server (`memory`) whose tools wrap delapan's library API (`resolve_tenant` → `select_preamble` / `resolve_and_persist`) on the hermetic SQLite tier. A transport-adaptive write-back module targets MCP mutation tools when available, DataHub Python emitter aspects otherwise.

**Vision goals served:** open-core public story (submission depends on `delapan[local]`); grounding preserved end-to-end (`grounded_in` → DataHub URNs); self-correcting memory writes (resolver is the differentiator).

**Tech Stack:** Python 3.11, `delapan[local]` (SQLite + sqlite-vec), `claude-agent-sdk`, `acryl-datahub` (emitter + CLI), `mcp-server-datahub` via `uvx`, DataHub OSS quickstart (docker), pytest.

## Global Constraints

- Repo path: new standalone repo, outside the delapan working tree.
- License: Apache-2.0 from the first commit (hackathon rule).
- All submission code is new work; delapan is a disclosed pre-existing dependency (README section "Pre-existing code disclosure").
- DataHub quickstart must be ≥ 1.4.x (document operations); `mcp-server-datahub` ≥ v0.5.0 (mutation tools; latest is v0.6.0).
- delapan local tier only: `DELAPAN_DB_PATH` points into the repo's `.data/`; no Supabase creds anywhere in this repo.
- Tests are hermetic: monkeypatch `delapan.core.memory.persist.embed_batch` and `delapan.core.agent.preamble.embed_text` (both hit the AI gateway otherwise).
- Deadline gates: feature-complete Aug 6; video + writeup Aug 7–8; submit Aug 8–9.
- Commit after every green test cycle; conventional-commit messages.

---

### Task 1: Repo scaffold + delapan dependency verification (risk R2)

**Files:**
- Create: `pyproject.toml`, `LICENSE`, `README.md`, `.gitignore`, `datahub_memory/__init__.py`, `tests/conftest.py`, `tests/test_delapan_dep.py`

**Interfaces:**
- Produces: importable package `datahub_memory`; pytest fixture `local_delapan` (tmp SQLite store + fake embeddings) used by every later test file.

- [ ] **Step 1: Scaffold**

```bash
mkdir -p ~/Repositories/8star/datahub-memory/{datahub_memory,tests,demo,skills}
cd ~/Repositories/8star/datahub-memory && git init
curl -s https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE
```

`pyproject.toml`:

```toml
[project]
name = "datahub-memory"
version = "0.1.0"
description = "Grounded institutional memory for data teams: DataHub agent with delapan write-time-resolved memory"
requires-python = ">=3.11"
license = { text = "Apache-2.0" }
dependencies = [
    "delapan[local]",
    "claude-agent-sdk",
    "acryl-datahub",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "ruff"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

`.gitignore`: `.venv/`, `.data/`, `__pycache__/`, `*.db`

- [ ] **Step 2: Install and write the dependency smoke test**

```bash
python3.11 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

`tests/conftest.py`:

```python
import pytest


@pytest.fixture()
def local_delapan(tmp_path, monkeypatch):
    """Hermetic delapan: tmp SQLite DB + deterministic fake embeddings."""
    monkeypatch.setenv("DELAPAN_DB_PATH", str(tmp_path / "delapan.db"))
    monkeypatch.setenv("DELAPAN_BACKEND", "local")

    async def fake_embed_batch(texts):
        return [[hash(t) % 7 * 0.1 + 0.1] * 8 for t in texts]

    async def fake_embed_text(text):
        return (await fake_embed_batch([text]))[0]

    import delapan.core.memory.persist as persist_mod
    import delapan.core.agent.preamble as preamble_mod
    monkeypatch.setattr(persist_mod, "embed_batch", fake_embed_batch)
    monkeypatch.setattr(preamble_mod, "embed_text", fake_embed_text)
    yield
```

`tests/test_delapan_dep.py`:

```python
from delapan.mcp.tenancy import resolve_tenant
from delapan.store import get_store


def test_resolve_tenant_local(local_delapan):
    ctx = resolve_tenant("datahub-memory-test", "main", create=True)
    assert ctx.org_id == "local"
    assert ctx.kb_id
    store = get_store()
    assert store is not None
```

- [ ] **Step 3: Run — expect PASS** (`pytest tests/test_delapan_dep.py -v`). If `pip install delapan[local]` or the import fails, this is R2 firing: fix in delapan proper (its repo, through the seam) before continuing.

- [ ] **Step 4: README stub** — title, one-liner, "Pre-existing code disclosure: depends on delapan (Apache… check its LICENSE), an open-source engine by the entrant; all code in this repo is new work created during the submission period." Copy the spec into `docs/design.md`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: scaffold datahub-memory (Apache-2.0), verify delapan[local] hermetic path"`

---

### Task 2: DataHub quickstart env + mutation-gating verification (risk R1)

**Files:**
- Create: `demo/quickstart.sh`, `docs/R1-decision.md`

**Interfaces:**
- Produces: running DataHub at `http://localhost:9002` (UI) / `:8080` (GMS); env vars `DATAHUB_GMS_URL`, `DATAHUB_GMS_TOKEN`; a written R1 decision consumed by Task 5.

- [ ] **Step 1: Quickstart**

```bash
.venv/bin/pip install 'acryl-datahub[datahub-rest]'
.venv/bin/datahub docker quickstart          # pulls compose; wait for "DataHub is now running"
.venv/bin/datahub docker check
```

Expected: all containers healthy. Record the server version from the UI footer or `curl -s localhost:8080/config | python3 -m json.tool | grep version` → must be ≥ 1.4.x. If lower: `datahub docker quickstart --version <latest>` and recheck.

- [ ] **Step 2: Token + MCP server connectivity**

Generate a personal access token in the UI (Settings → Access Tokens), then:

```bash
export DATAHUB_GMS_URL=http://localhost:8080 DATAHUB_GMS_TOKEN=<token>
npx @modelcontextprotocol/inspector uvx mcp-server-datahub   # or: uvx mcp-server-datahub --help
```

List tools in the inspector. Record: (a) full tool list, (b) whether mutation tools (`save_document`, `update_description`, `add_tags`, proposal tools) appear against OSS GMS, (c) whether `TOOLS_IS_MUTATION_ENABLED=true` is required to expose them.

- [ ] **Step 3: Write `docs/R1-decision.md`** — one page: mutation tools available on OSS? yes → Task 5 primary transport is MCP; no → Task 5 primary transport is emitter aspects (`institutionalMemory` + `datasetProperties.description` + glossary term creation via emitter), MCP mutations noted as Cloud-only in README. Also record document-ops availability (needs 1.4.x).

- [ ] **Step 4: Commit** — `git add demo/quickstart.sh docs/R1-decision.md && git commit -m "chore: quickstart env + R1 mutation-gating decision"`

---

### Task 3: Demo scenario seed (emitter)

**Files:**
- Create: `demo/seed.py`, `demo/verify_seed.py`

**Interfaces:**
- Produces: four datasets on platform `demo` with lineage `raw_payments → stg_payments → fct_revenue → monthly_revenue`, schemas, descriptions (with `stg_payments` description EMPTY on purpose), a freshness-incident note on `raw_payments`, one sample query on `fct_revenue`. URNs follow `urn:li:dataset:(urn:li:dataPlatform:demo,<name>,PROD)` — Tasks 4/6/8 hardcode these.

- [ ] **Step 1: Write `demo/seed.py`** (refinement over spec: pure-emitter scenario replaces the DuckDB warehouse — same lineage realism, fewer moving parts; noted in README)

```python
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
```

- [ ] **Step 2: Write `demo/verify_seed.py`** — REST check that all four URNs resolve and lineage exists:

```python
import os, requests

def main():
    gms = os.environ["DATAHUB_GMS_URL"]
    headers = {"Authorization": f"Bearer {os.environ.get('DATAHUB_GMS_TOKEN','')}"}
    from demo.seed import URNS
    for urn in URNS.values():
        r = requests.get(f"{gms}/entities/{requests.utils.quote(urn, safe='')}",
                         headers=headers, timeout=10)
        assert r.status_code == 200, f"{urn}: {r.status_code}"
    print("seed verified: 4/4 entities resolvable")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run** — `python demo/seed.py && python demo/verify_seed.py` → `seed verified: 4/4`. Also eyeball lineage graph in the UI (screenshot for README).

- [ ] **Step 4: Commit** — `git commit -am "feat: demo catalog seed — revenue chain with lineage + seeded incident"`

---

### Task 4: Memory bridge (`datahub_memory/bridge.py`)

**Files:**
- Create: `datahub_memory/bridge.py`, `tests/test_bridge.py`

**Interfaces:**
- Consumes: delapan `resolve_tenant(project, kb, *, create=True) -> TenantContext`; `get_store()`; async `resolve_and_persist(ctx, store, candidates: list[Finding], cfg) -> ResolutionOutcome`; async `select_preamble(query, *, store, kb_id) -> tuple[str, str]`; `Finding(exploration_id, project_id, kb, category, title, content: dict, confidence, tags, provenance)`.
- Produces (used by Task 6 tools and Task 8 drift demo):
  - `snapshot_hash(schema_fields: list[dict], upstream_urns: list[str]) -> str`
  - `build_finding(question: str, conclusion: str, category: str, grounded: list[dict]) -> Finding` — each `grounded` item `{urn, snapshot_hash, ui_url}`
  - `persist(project: str, kb: str, findings: list[Finding]) -> dict` — `{"ops": [{"op","title","reason"}], "affected_ids": [...]}`
  - `recall(project: str, kb: str, query: str) -> dict` — `{"coverage": "rich|sparse|gap", "preamble": "<xml>"}`
  - `check_drift(content: dict, current: dict[str, str]) -> list[str]` — URNs whose hash changed

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bridge.py
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
```

- [ ] **Step 2: Run — expect FAIL** (`pytest tests/test_bridge.py -v`, module missing).

- [ ] **Step 3: Implement `datahub_memory/bridge.py`**

```python
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
    ctx = resolve_tenant("_shape_only", "_shape_only", create=False) if False else None  # noqa: F841
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
    return {
        "ops": [{"op": e.op, "title": e.candidate_title, "reason": e.reason}
                for e in outcome.events],
        "affected_ids": list(outcome.affected_finding_ids),
    }


def recall(project: str, kb: str, query: str) -> dict:
    ctx = resolve_tenant(project, kb, create=True)
    store = get_store()
    xml, coverage = asyncio.run(select_preamble(query, store=store, kb_id=ctx.kb_id))
    return {"coverage": coverage, "preamble": xml}


def check_drift(content: dict, current: dict[str, str]) -> list[str]:
    return [g["urn"] for g in content.get("grounded_in", [])
            if g["urn"] in current and current[g["urn"]] != g["snapshot_hash"]]
```

Note for the implementer: delete the dead `ctx = ...` line in `build_finding` (shown struck to emphasize `project_id` is resolved at persist time, not build time). If `ResolutionOutcome` field names differ (`events` / `affected_finding_ids`), read `delapan/core/memory/models.py` and adjust the two attribute accesses in `persist` — the test is the contract, not the attribute names.

- [ ] **Step 4: Run — expect 4 PASS.** If `Finding` requires `project_id` non-empty, pass `project_id=ctx.project_id` by moving construction into `persist` (keep `build_finding` returning a dict then) — adjust test imports accordingly and re-run.

- [ ] **Step 5: Commit** — `git commit -am "feat: memory bridge — grounded findings, persist/recall, drift check"`

---

### Task 5: Write-back (`datahub_memory/writeback.py`)

**Files:**
- Create: `datahub_memory/writeback.py`, `tests/test_writeback.py`

**Interfaces:**
- Consumes: `docs/R1-decision.md` (transport choice), `DATAHUB_GMS_URL`/`DATAHUB_GMS_TOKEN`.
- Produces (used by Task 6):
  - `write_report(urn: str, title: str, markdown: str) -> dict` — attaches the investigation report (institutionalMemory link element whose description carries the summary; or MCP `save_document` if R1 said available)
  - `fill_description(urn: str, description: str) -> dict`
  - Both return `{"ok": bool, "transport": "mcp"|"emitter", "detail": str}`

- [ ] **Step 1: Write the failing tests** (emitter transport, mocked emitter)

```python
# tests/test_writeback.py
from unittest.mock import MagicMock, patch
from datahub_memory import writeback


@patch("datahub_memory.writeback._emitter")
def test_fill_description_emits_properties(mock_em):
    em = MagicMock(); mock_em.return_value = em
    out = writeback.fill_description("urn:li:dataset:x", "Staged payments, USD-normalized.")
    assert out["ok"] and out["transport"] == "emitter"
    aspect = em.emit.call_args[0][0].aspect
    assert aspect.description == "Staged payments, USD-normalized."


@patch("datahub_memory.writeback._emitter")
def test_write_report_appends_institutional_memory(mock_em):
    em = MagicMock(); mock_em.return_value = em
    out = writeback.write_report("urn:li:dataset:x", "Trust check: monthly_revenue",
                                 "## Verdict\nTrusted with caveat.")
    assert out["ok"]
    aspect = em.emit.call_args[0][0].aspect
    assert "Trust check" in aspect.elements[-1].description
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
"""Write distilled knowledge back to DataHub. Transport: emitter (OSS-safe).
If docs/R1-decision.md recorded MCP mutations as available on OSS, the agent
prefers the DataHub MCP mutation tools directly and this module is the fallback."""
from __future__ import annotations

import os
import time

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    AuditStampClass, DatasetPropertiesClass,
    InstitutionalMemoryClass, InstitutionalMemoryMetadataClass,
)


def _emitter() -> DatahubRestEmitter:
    return DatahubRestEmitter(gms_server=os.environ["DATAHUB_GMS_URL"],
                              token=os.environ.get("DATAHUB_GMS_TOKEN"))


def fill_description(urn: str, description: str) -> dict:
    _emitter().emit(MetadataChangeProposalWrapper(
        entityUrn=urn, aspect=DatasetPropertiesClass(description=description)))
    return {"ok": True, "transport": "emitter", "detail": f"description set on {urn}"}


def write_report(urn: str, title: str, markdown: str) -> dict:
    stamp = AuditStampClass(time=int(time.time() * 1000),
                            actor="urn:li:corpuser:datahub-memory")
    element = InstitutionalMemoryMetadataClass(
        url=f"https://github.com/anthonysuherli/dh8#report",
        description=f"{title} — {markdown[:900]}", createStamp=stamp)
    _emitter().emit(MetadataChangeProposalWrapper(
        entityUrn=urn, aspect=InstitutionalMemoryClass(elements=[element])))
    return {"ok": True, "transport": "emitter", "detail": f"report attached to {urn}"}
```

Implementer note: `InstitutionalMemoryClass(elements=[...])` REPLACES the aspect; to append, first GET the current aspect via `datahub.ingestion.graph.client.DataHubGraph.get_aspect` and concatenate — do that (read-modify-write) and assert in the test that the seeded incident element survives (extend the mock accordingly). If R1 said MCP mutations work on OSS, the agent's system prompt (Task 6) routes writes through the DataHub MCP tools and these functions stay as the tested fallback.

- [ ] **Step 4: Run — expect PASS**, then a live smoke against quickstart: `python -c "from datahub_memory.writeback import fill_description; print(fill_description('<stg_payments urn>', 'smoke'))"` and check the UI.

- [ ] **Step 5: Commit** — `git commit -am "feat: write-back — description fill + institutional-memory report (emitter transport)"`

---

### Task 6: Agent loop (`datahub_memory/agent.py`)

**Files:**
- Create: `datahub_memory/agent.py`, `datahub_memory/prompts.py`, `tests/test_routing.py`

**Interfaces:**
- Consumes: Task 4 bridge functions, Task 5 writeback functions, `uvx mcp-server-datahub` (stdio), env `ANTHROPIC_API_KEY`, `DATAHUB_GMS_URL`, `DATAHUB_GMS_TOKEN`.
- Produces: `route(coverage: str) -> str` (`"answer_from_memory"` for rich, else `"investigate"`); async `run_question(question: str, project: str = "dh-demo", kb: str = "main") -> dict` — `{"answer", "mode", "counters": {"turns", "tool_calls", "duration_s"}}`. CLI: `python -m datahub_memory "<question>"`.

- [ ] **Step 1: Failing routing test**

```python
# tests/test_routing.py
from datahub_memory.agent import route

def test_route():
    assert route("rich") == "answer_from_memory"
    assert route("sparse") == "investigate"
    assert route("gap") == "investigate"
```

- [ ] **Step 2: Run — FAIL.** Then implement:

`datahub_memory/prompts.py`:

```python
SYSTEM = """You are Data Memory, an investigation agent for data teams.

Policy — memory first:
1. ALWAYS call memory_recall with the user's question first.
2. If coverage is 'rich': answer ONLY from the preamble. Cite finding ids and
   DataHub URNs. Do not call any DataHub tool.
3. Otherwise investigate via the datahub tools: search -> get_entities ->
   get_lineage (walk upstream) -> read descriptions/institutional memory ->
   get_dataset_queries when SQL context helps.
4. Conclude, then: (a) memory_persist one finding per distinct conclusion with
   every DataHub URN you relied on (include each entity's schema fields and
   upstream urns so grounding hashes are computed); (b) write back: fill any
   empty description you can now write authoritatively (writeback_description)
   and attach your report to the subject entity (writeback_report).
5. Every answer ends with a 'Grounded in:' list of URNs.
Answers are concise; verdicts explicit (trusted / trusted-with-caveat / not trusted)."""
```

`datahub_memory/agent.py`:

```python
"""One agent, two tool surfaces: DataHub MCP (stdio) + in-process memory tools."""
from __future__ import annotations

import json
import os
import time

from claude_agent_sdk import (
    ClaudeAgentOptions, create_sdk_mcp_server, query, tool,
)

from datahub_memory import bridge, writeback
from datahub_memory.prompts import SYSTEM


def route(coverage: str) -> str:
    return "answer_from_memory" if coverage == "rich" else "investigate"


@tool("memory_recall", "Tap the KB for prior grounded knowledge about a question",
      {"project": str, "kb": str, "query": str})
async def memory_recall(args):
    out = bridge.recall(args["project"], args["kb"], args["query"])
    out["route"] = route(out["coverage"])
    return {"content": [{"type": "text", "text": json.dumps(out)}]}


@tool("memory_persist", "Persist an investigation conclusion as a grounded finding",
      {"project": str, "kb": str, "question": str, "conclusion": str,
       "category": str, "grounded": list})
async def memory_persist(args):
    grounded = [
        {"urn": g["urn"],
         "snapshot_hash": bridge.snapshot_hash(g.get("schema_fields", []),
                                               g.get("upstream_urns", [])),
         "ui_url": g.get("ui_url", "")}
        for g in args["grounded"]
    ]
    f = bridge.build_finding(args["question"], args["conclusion"],
                             args["category"], grounded)
    out = bridge.persist(args["project"], args["kb"], [f])
    return {"content": [{"type": "text", "text": json.dumps(out)}]}


@tool("writeback_description", "Fill an empty/stale dataset description in DataHub",
      {"urn": str, "description": str})
async def writeback_description(args):
    return {"content": [{"type": "text",
                         "text": json.dumps(writeback.fill_description(**args))}]}


@tool("writeback_report", "Attach the investigation report to a DataHub entity",
      {"urn": str, "title": str, "markdown": str})
async def writeback_report(args):
    return {"content": [{"type": "text",
                         "text": json.dumps(writeback.write_report(**args))}]}


MEMORY_SERVER = create_sdk_mcp_server(
    name="memory", version="0.1.0",
    tools=[memory_recall, memory_persist, writeback_description, writeback_report])


async def run_question(question: str, project: str = "dh-demo", kb: str = "main") -> dict:
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM,
        mcp_servers={
            "memory": MEMORY_SERVER,
            "datahub": {"command": "uvx", "args": ["mcp-server-datahub"],
                        "env": {"DATAHUB_GMS_URL": os.environ["DATAHUB_GMS_URL"],
                                "DATAHUB_GMS_TOKEN": os.environ.get("DATAHUB_GMS_TOKEN", "")}},
        },
        allowed_tools=["mcp__memory__*", "mcp__datahub__*"],
        max_turns=25,
    )
    t0, turns, tool_calls, answer = time.time(), 0, 0, ""
    async for message in query(prompt=f"{question}\n(project={project}, kb={kb})",
                               options=options):
        kind = type(message).__name__
        if kind == "AssistantMessage":
            turns += 1
            for block in message.content:
                if type(block).__name__ == "ToolUseBlock":
                    tool_calls += 1
                elif type(block).__name__ == "TextBlock":
                    answer = block.text
    return {"answer": answer, "mode": "agent",
            "counters": {"turns": turns, "tool_calls": tool_calls,
                         "duration_s": round(time.time() - t0, 1)}}
```

`datahub_memory/__main__.py`:

```python
import asyncio, json, sys
from datahub_memory.agent import run_question

out = asyncio.run(run_question(" ".join(sys.argv[1:]) or "Can I trust monthly_revenue?"))
print(out["answer"]); print(json.dumps(out["counters"]))
```

- [ ] **Step 3: Run routing test — PASS.** Implementer note: the SDK message/block class names and `ClaudeAgentOptions` fields above are from the claude-agent-sdk docs as of writing — verify against the installed version's README on first run and adjust the isinstance-by-name checks to real imports (`from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock`).

- [ ] **Step 4: Live spike (the D1–2 gate):** `python -m datahub_memory "Can I trust monthly_revenue for the board report?"` against the seeded quickstart. Expected: agent recalls (gap) → investigates via datahub tools → answers citing the Jul 24 incident → persists 1–2 findings (ops ADD) → fills `stg_payments` description → attaches report. Verify in DataHub UI + `sqlite3 .data/delapan.db "select title from findings"`.

- [ ] **Step 5: Run it AGAIN (inheritance proof):** same question → recall returns `rich` → answer from memory, `tool_calls` ≤ 2, no DataHub reads. Save both counter lines to `demo/counters-baseline.json`.

- [ ] **Step 6: Commit** — `git commit -am "feat: agent loop — memory-first routing over DataHub MCP + in-process memory tools"`

---

### Task 7: Drift demo + scenario runner

**Files:**
- Create: `demo/drift.py`, `demo/run_demo.sh`

**Interfaces:**
- Consumes: Task 3 URNs/FIELDS, Task 6 CLI.
- Produces: `demo/drift.py` (re-emits `stg_payments` schema with `amount_usd` renamed to `amount`), `demo/run_demo.sh` (beats 1–3 in order, printing counters between).

- [ ] **Step 1: `demo/drift.py`** — import `FIELDS`, `URNS`, `_schema` from `demo.seed`; mutate `FIELDS["stg_payments"]` to `[("payment_id","string"),("amount","number"),("paid_date","string")]`; re-emit that one schema aspect; print "drift emitted".

- [ ] **Step 2: `demo/run_demo.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
Q="Can I trust monthly_revenue for the board report?"
echo "=== BEAT 1: investigate ===";  python -m datahub_memory "$Q"
echo "=== BEAT 2: inherit ===";      python -m datahub_memory "$Q"
echo "=== BEAT 3: drift ===";        python demo/drift.py
python -m datahub_memory "$Q (re-verify: upstream schema may have changed)"
```

- [ ] **Step 3: Run end-to-end.** Beat 3 expected: recall shows prior finding, agent detects hash mismatch via fresh schema fetch + memory_persist → resolver emits **SUPERSEDE** (visible in ops output), report updated. If the resolver returns UPDATE instead of SUPERSEDE for the contradiction, capture whichever op fires and script the narration around the actual behavior — the bi-temporal retirement is the point, not the op label.

- [ ] **Step 4: Commit** — `git commit -am "feat: drift demo + scripted 3-beat scenario"`

---

### Task 8: Claude Code plugin packaging

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `skills/investigate/SKILL.md`, `skills/recall/SKILL.md`, `skills/writeback/SKILL.md`, `mcp.json`

**Interfaces:**
- Consumes: the delapan plugin as the reference layout (`delapan-ai/backend/.claude-plugin/`, `mcp.json`, `skills/` — copy the structure, not the content) and the 2026-07-26 plugin release-interface spec.
- Produces: installable plugin — `claude plugin marketplace add anthonysuherli/dh8 && claude plugin install datahub-memory@datahub-memory`, exposing `/datahub-memory:investigate|recall|writeback`.

- [ ] **Step 1:** Copy the layout of delapan's plugin shell; `mcp.json` starts BOTH servers (memory via `python -m datahub_memory.mcp_stub` — a 10-line stdio wrapper around `MEMORY_SERVER`; datahub via uvx). Each SKILL.md: trigger description + the workflow section of `prompts.SYSTEM` split per command.
- [ ] **Step 2:** Install locally, run `/datahub-memory:investigate` in a scratch Claude Code session against the quickstart; verify same behavior as CLI.
- [ ] **Step 3: Commit** — `git commit -am "feat: Claude Code plugin packaging"`

---

### Task 9: Upstream contribution (bonus criterion)

**Files:**
- Create (in a fork of `datahub-project/datahub-skills`): one new skill directory, e.g. `skills/grounded-investigation/SKILL.md`

**Interfaces:** none downstream; the PR link goes in the README + Devpost text.

- [ ] **Step 1:** Clone their repo, read 2–3 existing skills for house format.
- [ ] **Step 2:** Write a **vendor-neutral** `grounded-investigation` skill: chain search → get_entities → get_lineage → institutional memory → conclude with URN citations → write back via mutation tools/proposals. (It's the investigation half of Task 6's prompt, theirs to keep; no delapan dependency.)
- [ ] **Step 3:** Open the PR; reference it from README ("Upstream contribution"). If maintainers are slow, the open PR itself satisfies the criterion.

---

### Task 10: Submission package

**Files:**
- Create: `README.md` (full), `demo/counters.md`, Devpost draft text, video.

- [ ] **Step 1: README** — problem, 90-second quickstart (docker quickstart → seed → ask), architecture diagram (ASCII, from the spec §3), **measured table** from `demo/counters-baseline.json` (beat 1 vs beat 2: tool calls / turns / seconds), pre-existing-code disclosure, R1 decision note, license badge.
- [ ] **Step 2: Video** — use the `terminal-demo-video` skill on `demo/run_demo.sh` beats + browser cuts of the DataHub UI (description filled, report attached, before/after drift). ≤3 min, hosted YouTube unlisted-public.
- [ ] **Step 3: Clean-machine reproduce** — fresh venv on a second machine/user account, follow README verbatim; fix anything that snags.
- [ ] **Step 4: Devpost submission** — text description, video link, repo link, testing instructions (token generation note), sample outputs (one agent-authored report + resolution log excerpt). Submit **Aug 8–9**, not deadline day. Complete the feedback survey.

---

## Self-review (done at write time)

- **Spec coverage:** §2 constraints → Task 1/10; R1/R2 → Tasks 2/1; seed+demo env → Task 3 (DuckDB refined to pure emitter — noted); bridge/§3 memory+drift → Task 4; write-back → Task 5; agent+recall routing → Task 6; demo beats → Tasks 6–7; counters → Tasks 6/10; plugin → Task 8; upstream PR → Task 9; video/README/writeup → Task 10. Glossary-term proposals (spec §3) are folded into Task 5's implementer note: MCP-transport if R1 allows, else dropped as a stretch — record whichever in R1-decision.md and README.
- **Placeholder scan:** implementer notes flag the three genuinely-verify-at-runtime seams (SDK class names, ResolutionOutcome attrs, institutionalMemory read-modify-write) with the exact adjustment to make — no bare TBDs.
- **Type consistency:** `bridge.persist` returns `{"ops", "affected_ids"}` and Task 6's `memory_persist` passes it through verbatim; `grounded` item shape `{urn, schema_fields, upstream_urns, ui_url}` in the tool matches `snapshot_hash(schema_fields, upstream_urns)` and `build_finding`'s `{urn, snapshot_hash, ui_url}` after transformation. `route()` consumed only by prompt policy + test.
