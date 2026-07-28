# Design: "Data Memory" — DataHub Agent Hackathon submission

**Date:** 2026-07-27
**Status:** Original design draft (2026-07-27), superseded in places by what shipped — see README.md and docs/R1-decision.md for current behavior.
**Target:** [Build with DataHub: The Agent Hackathon](https://datahub.devpost.com/) — Challenge 1
("Agents That Do Real Work"), deadline **Aug 10, 2026, 5:00pm EDT**, judging Aug 17–31.

**Vision goals served:** the open-core public story (SQLite local tier as the free,
zero-credential distribution — the submission depends on `delapan[local]` and demos it
to a new audience); "Grounding preserved end to end" (`grounded_in` provenance carried
into a new domain: DataHub URNs); "Self-correcting memory writes" (the shipped
ADD/UPDATE/NOOP/SUPERSEDE resolver is the submission's differentiator). The submission
is a **companion artifact** — a new standalone repo consuming delapan as a dependency —
not an engine feature; no delapan invariant is touched. Any engine change it motivates
flows through the `Store` seam as normal delapan work.

---

## 1. One-liner

An agent that investigates data questions by walking DataHub (search → lineage →
schemas → real SQL), persists every conclusion as a delapan finding `grounded_in`
DataHub URNs, and writes distilled knowledge **back** to DataHub (documents,
descriptions, glossary proposals) — so the next user or agent **inherits** the answer
instead of re-deriving it.

Challenge 1's own framing — agents that "read DataHub metadata … take action, and
write results back, enabling knowledge inheritance across users/agents" — is this
system's literal description.

## 2. Hackathon constraints honored

- **New work only:** all submission code (adapter, agent, skills, plugin, demo kit) is
  written during the submission period. delapan is disclosed as a pre-existing
  open-source dependency owned by the entrant (`pip install "delapan[local]"`).
- **Apache-2.0 public repo** — new standalone repo (working name `datahub-memory`),
  licensed Apache-2.0 from the first commit.
- **Required DataHub surface:** uses the **MCP Server** (primary) and **DataHub
  Skills** (the plugin form + upstream contribution). Two of the four qualifying
  surfaces.
- **Required artifacts:** working app, <3-min video (YouTube), text description,
  testing instructions, sample outputs (agent-authored DataHub documents + resolution
  log).

### Judging criteria mapping (six, equally weighted)

| Criterion | How this submission scores it |
|---|---|
| 1. Use of DataHub | Reads (search, lineage, schemas, SQL context) **and writes back** (documents, descriptions, glossary proposals through the HITL approval workflow) — the criterion's explicit "strongest submissions contribute back to the graph" tell |
| 2. Technical execution | Engine heavy-lifting is mature shipped code (resolver, coverage bands, provenance); new code is a thin, testable adapter + agent loop |
| 3. Originality | No entrant pairs a write-time-deduplicating memory engine with a catalog; drift-supersede on camera is unique |
| 4. Real-world usefulness | Tribal-knowledge loss / repeated re-investigation is a core data-team pain; second-question-is-instant is directly demonstrable |
| 5. Submission quality | Scripted 4-beat video (terminal-demo-video skill), measured before/after numbers in README |
| 6. Bonus: OSS contribution | One PR to `datahub-project/datahub-skills` (37-star repo — maintainers are the judges) |

## 3. Architecture

```
  user question
       │
       ▼
  Investigation agent  (Claude Agent SDK runner; also packaged as Claude Code plugin)
       │  skills: /investigate  /recall  /writeback
       │
       ├──► delapan MCP  ──► delapan[local] (SQLite tier)
       │      delapan_resume (coverage band)   ← recall path
       │      resolve_and_persist (ADD/UPDATE/NOOP/SUPERSEDE)  ← memory writes
       │
       └──► DataHub MCP  ──► DataHub OSS quickstart (docker)
              search / get_entities / get_lineage / find_sql_context …  ← reads
              save_document / update_description / glossary proposals   ← write-back
```

- **Two MCP servers, one agent.** DataHub's `mcp-server-datahub` (v0.6.0, empirically
  20 tools with mutations on and a non-empty Document catalog: 8 read / 12 write —
  see `docs/R1-decision.md`'s tool inventory) and delapan's MCP server run side by
  side; the agent loop is the only new orchestration code.
- **Memory bridge:** delapan project = DataHub instance; KB per domain. Every finding's
  `grounded_in` carries the DataHub URNs (+ a lightweight snapshot marker: schema/lineage
  hash at capture time) it was derived from.
- **Preamble-first recall:** every question first calls `delapan_resume(query)`.
  `rich` → answer from memory citing prior investigations + URNs, zero warehouse work.
  `sparse`/`gap` → full investigation, then persist + write back.
- **Drift supersede:** if the current schema/lineage hash of a finding's grounded URNs
  differs from its capture marker, the re-investigation's resolver call SUPERSEDEs the
  stale finding (bi-temporal — retired, never deleted) and the write-back document is
  updated.
- **Write-back loop:** investigation report → `save_document` attached to the subject
  entities; empty/stale descriptions → `update_description`; candidate glossary terms →
  **proposals** so a human approves in the DataHub UI (their HITL surface, shown in the
  demo).

## 4. Components (all new code unless marked)

| Unit | Purpose | Depends on |
|---|---|---|
| `agent/` — investigation loop | Claude Agent SDK runner; routes recall→investigate→persist→write-back | both MCP servers |
| `skills/` — `/investigate`, `/recall`, `/writeback` | workflow instructions (Claude Code skill format) | agent |
| `bridge/` — memory bridge | URN-grounded finding construction, snapshot markers, drift check | delapan (pre-existing, disclosed) |
| `writeback/` — DataHub writer | doc/description/proposal calls; falls back to Python emitter/GraphQL if MCP mutations are Cloud-gated (risk R1) | DataHub SDK |
| `demo/` — demo kit | docker-compose quickstart pin, seed script (sample metadata + small DuckDB warehouse for real lineage), scripted scenario | DataHub OSS |
| plugin packaging | Claude Code plugin form of the same agent (port of delapan's plugin rails + 2026-07-26 release-interface spec) | existing rails |
| upstream PR | one contribution to `datahub-project/datahub-skills` (likely a generic grounded-investigation skill; final target chosen in-repo) | — |

## 5. Demo script (3-min video, 4 beats)

1. **Investigate:** "Can I trust `monthly_revenue` for the board report?" → agent walks
   lineage, finds the seeded upstream issue, answers with URN-cited provenance; document
   + description proposal appear in the DataHub UI.
2. **Inherit:** fresh session, related question → `rich` preamble → instant answer
   citing beat 1's investigation. On-screen counters: tool calls / tokens / latency,
   investigation #1 vs #2.
3. **Drift:** seed script mutates the upstream schema → re-ask → SUPERSEDE event on
   camera; DataHub document updates; old finding retired, not deleted.
4. **Close:** DataHub UI showing agent-authored, human-approved knowledge; delapan
   graph canvas of the accumulated institutional memory.

## 6. Testing & verification

- Unit tests: bridge + write-back against a mocked DataHub client; delapan on the
  hermetic SQLite tier (no cloud creds anywhere in the submission).
- Smoke script: end-to-end against the local quickstart (not CI — documented manual
  gate before each demo take).
- Measured claims: the beat-2 counters are produced by a small script, committed with
  its output — no hand-waved numbers in the README.
- Judge reproducibility: one-command `docker compose up` + seed + `uvx` run,
  README-verified on a clean machine before submission.

## 7. Risks

- **R1 — MCP mutation gating (verify Day 1):** findings indicate mutation tools need
  `mcp-server-datahub` v0.5.0+ *and DataHub Cloud v0.3.17+*; if writes are Cloud-only
  over MCP, `writeback/` swaps to the OSS Python emitter/GraphQL — write-back survives,
  only the transport changes. Documents additionally need DataHub 1.4.x+ — pin the
  quickstart image accordingly (verify same day).
- **R2 — delapan install path:** `pip install "delapan[local]"` must work clean on a
  fresh machine (judges). Verified Day 1; fixed in delapan proper if broken (normal
  engine work, through the seam).
- **R3 — timeline compression:** fallback ladder — drop the upstream PR first, then
  the plugin form; the memory loop alone is a complete Challenge 1 submission.
- **R4 — engine API spend:** exploration/answering runs consume gateway credits
  (402'd once already on 2026-07-27); demo takes are scripted to bound spend.

## 8. Timeline (Jul 28 → Aug 10; submit Aug 8–9)

| Days | Work |
|---|---|
| D1–2 | Quickstart env + seed data; **R1/R2 verifications**; spike: one agent turn against both MCPs |
| D3–5 | Investigation agent + memory bridge + write-back loop |
| D6–7 | Recall path + drift supersede; counters script |
| D8 | Plugin packaging |
| D9 | Upstream `datahub-skills` PR |
| D10–11 | Video (terminal-demo-video), README, Devpost writeup, clean-machine reproduce |
| D12+ | Buffer; feedback survey; submit early |

## 9. Out of scope

- DataHub Cloud features beyond what OSS quickstart offers (unless R1 forces a Cloud
  trial for mutations — decision recorded when verified).
- Any delapan engine refactor; changes land in delapan only if the integration
  surfaces a genuine engine bug (through the `Store` seam, as ordinary delapan work).
- Multi-warehouse / production-scale ingestion; the demo warehouse is deliberately
  small and legible.
- Challenge 2/3 angles (codegen, ML lineage) — Challenge 1 only.
