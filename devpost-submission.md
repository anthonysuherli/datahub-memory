# Devpost submission text — datahub-memory

Ready-to-paste copy for the Devpost submission form. **Build with DataHub: The Agent Hackathon**, Challenge 1 ("Agents That Do Real Work").

## Devpost form fields

Field-by-field, in the order the Devpost form asks. Everything here is ready to paste as-is.

| Form field | Value |
|---|---|
| **Project name** | `datahub-memory` |
| **Elevator pitch** (short tagline field; Devpost limits it — this is 156 chars, comfortably inside) | Makes DataHub your team's institutional knowledge base: an agent investigates once, and the answer lands in the catalog where the next person already looks. |
| **Video demo link** | https://youtu.be/d-R0-WuPzXw |
| **"Try it out" links** | 1. https://github.com/anthonysuherli/datahub-memory<br>2. https://github.com/datahub-project/datahub-skills/pull/62<br>3. https://github.com/datahub-project/datahub-skills/pull/69 |
| **Built With** (tags) | `python` · `claude-code` · `model-context-protocol` · `mcp` · `datahub` · `anthropic` · `claude` · `sqlite` · `docker` · `delapan` |
| **Image gallery** | `docs/assets/hero.gif` (lead — the measured 16 → 1 comparison) |
| **Project story** | The `## Judge snapshot` … `## What's next` sections below, pasted in order. |

**Additional info tab is complete** (verified live 2026-07-31): challenge category, repo URL, project URL (`#quickstart-for-judges`), examples/ link, DataHub technologies (OSS / Core Platform + MCP Server + Skills), the upstream-contribution write-up, country, the pre-existing-code disclosure, and all four feedback-prize answers. No empty fields remain on that tab.

**Before submitting, confirm the YouTube video's visibility is Public** — not Unlisted. An unlisted video is reachable by URL, so the link working is not proof; check it in YouTube Studio. The rules require public.

### Elevator pitch — longer form

datahub-memory makes DataHub your team's **institutional knowledge base**, not just a schema registry. An agent investigates a question once — walking lineage, schemas, incidents — and the conclusion lands back in the catalog through DataHub's own mutation tools (`update_description`, `save_document`), where the next person already looks.

Underneath that is a **memory layer, not an agent**: five MCP tools give an agent somewhere to put
what it concludes. Findings are grounded in DataHub URNs and structural snapshot hashes; on an
explicit re-verification request, the system compares those hashes with current catalog metadata and
can retire a stale version without deleting its history.

**The sharing boundary is explicit:** one-call warm recall uses a local SQLite store; team-visible
sharing happens through the description and Document written to DataHub. SQLite makes the demo
self-contained with no external persistence service, DataHub Cloud license, or warehouse. Model
calls still require `AI_GATEWAY_API_KEY`.

Three Claude Code skills ship on top of it — `/datahub-memory:investigate` (the flagship: recall first, walk lineage/schemas/documents only where memory is thin, persist, write back), `/datahub-memory:recall` (memory-only lookup with the freshness check), and `/datahub-memory:writeback`. The investigation agent is the headline consumer of the memory layer, not the product itself — which is the whole point: the layer doesn't care which agent is calling it.

Measured live against DataHub OSS quickstart, the first investigation took 16 total agent tool calls
and 127.2 seconds; the same question with a fresh Claude context and the same local store took one
`memory_recall` call and 20.9 seconds: **16× fewer tool calls and ~6× faster**. The patterns are
proposed upstream in two open DataHub Skills PRs:
[#62 `datahub-investigate`](https://github.com/datahub-project/datahub-skills/pull/62) and
[#69 `datahub-memory`](https://github.com/datahub-project/datahub-skills/pull/69).

---

## Judge snapshot — Challenge 1: Agents That Do Real Work

[![Open upstream PR #62](https://img.shields.io/badge/DataHub_Skills-PR_%2362_open-0969da?style=flat-square&logo=github)](https://github.com/datahub-project/datahub-skills/pull/62)
[![Open upstream PR #69](https://img.shields.io/badge/DataHub_Skills-PR_%2369_open-0969da?style=flat-square&logo=github)](https://github.com/datahub-project/datahub-skills/pull/69)

The official Challenge 1 loop is **read DataHub → act → write results back so the next person or
agent inherits the context**. datahub-memory implements that loop directly:

| Read | Act | Write back |
|---|---|---|
| Search, lineage, schemas, and Documents through `mcp-server-datahub` | Recall, investigate gaps, ground conclusions, and explicitly re-verify structural snapshots | `update_description` and `save_document` publish the shared result into DataHub |

### Measured result

| Run | Total agent tool calls | Duration | What happened |
|---|---:|---:|---|
| **Cold — first investigation** | 16 | 127.2s | Catalog walk, findings persisted, description + report written back |
| **Warm — same local store, fresh Claude context** | **1** | **20.9s** | One `memory_recall`; zero DataHub calls |

**16× fewer tool calls, ~6× faster.** Source:
[`demo/counters-baseline.json`](https://github.com/anthonysuherli/datahub-memory/blob/main/demo/counters-baseline.json).
This is a measured execution comparison, not a claim of 16× lower LLM cost.

### Fast audit — no setup

1. [Watch the 2:31 demo](https://youtu.be/d-R0-WuPzXw): write-back at
   [0:50](https://youtu.be/d-R0-WuPzXw?t=50), warm recall at
   [0:58](https://youtu.be/d-R0-WuPzXw?t=58), correction at
   [2:00](https://youtu.be/d-R0-WuPzXw?t=120).
2. [Read the exact artifacts written into DataHub](https://github.com/anthonysuherli/datahub-memory/blob/main/examples/datahub-writebacks.md).
3. [Inspect grounded answers and snapshot hashes](https://github.com/anthonysuherli/datahub-memory/blob/main/examples/investigation-answer.md).
4. [Inspect resolver history](https://github.com/anthonysuherli/datahub-memory/blob/main/examples/resolution-log.md)
   and the [retirement-gate output](https://github.com/anthonysuherli/datahub-memory/blob/main/examples/verify-only-output.md).

### Rubric map

| Official criterion | Evidence |
|---|---|
| **Use of DataHub** | Reads the context graph through the MCP Server and contributes a description and attached Document back to it. |
| **Technical execution** | Reproducible three-beat runner, structural hashing, write-time reconciliation, and a database-state gate. |
| **Originality** | Adds persistent, recall-first conclusions instead of rebuilding DataHub's catalog features. |
| **Real-world usefulness** | Reduces repeated trust investigations while publishing the team-visible result on the catalog entity. |
| **Submission quality** | Sub-3-minute demo, verbatim samples, automated setup, and fast-audit/full-run paths. |
| **Open-source bonus** | Two open PRs to DataHub's official Skills Registry: #62 and #69. |

## Inspiration

Every data team re-derives the same answers. Someone investigates whether `monthly_revenue` can be trusted, traces the incident that touched it, checks the schema — and a month later, a different person (or agent) asks the exact same question and starts from zero, because the investigation lived in a Slack thread or a person's head, not in the catalog. DataHub already models the connective tissue (lineage, schema, institutional memory) that makes an investigation possible; what's missing is a place for the *conclusions* to live, grounded enough to trust and fresh enough to act on. Challenge 1's own framing — agents that read metadata, take action, and write results back so knowledge inherits across users and agents — is exactly this gap.

datahub-memory pairs DataHub's MCP surface with
[delapan](https://github.com/anthonysuherli/delapan), a disclosed pre-existing memory engine owned by
the entrant. Each local finding carries DataHub URNs and structural snapshot hashes; the shared
description and report live in DataHub itself.

## What it does

`datahub-memory` is a memory layer whose shared output surface is the catalog itself. An agent that calls its five tools gets:

1. **Somewhere to put a conclusion** — `memory_persist` stores a local finding whose `grounded_in` field carries DataHub URNs plus a structural snapshot hash. When enabled, delapan's LLM-backed resolver attempts ADD / UPDATE / NOOP / SUPERSEDE reconciliation at write time.
2. **Memory-first answers** — `memory_recall` returns a preamble plus a coverage band (`rich` / `sparse` / `gap`) and route. On `rich` or `sparse`, the caller can answer from the local finding with zero new DataHub calls.
3. **On-demand structural staleness detection** — when the question explicitly asks to re-verify, `check_freshness` compares every recorded hash with current field paths/types and upstream URNs, then reports which snapshots changed.
4. **A path back into the catalog** — `writeback_description` / `writeback_report` push what was learned into DataHub itself, so the next investigator — human or agent — inherits the answer from the catalog rather than from this tool's private store.

The `/datahub-memory:investigate` skill is what sequences those into an investigation: recall first, walk DataHub through `mcp-server-datahub` (search → lineage → schema → documents) only where memory is thin, persist 2-4 grounded findings, hand off to write-back. `/datahub-memory:recall` and `/datahub-memory:writeback` are two smaller consumers of the same layer — and nothing stops a third-party agent from being another.

Measured on a live three-beat run, a fresh Claude context with the same local store needs one tool
call and 20.9 seconds instead of 16 tool calls and 127.2 seconds. In beat 3, the prompt explicitly
requests re-verification after the cataloged schema changes; `check_freshness` detects the changed
snapshot, the stale finding is retired with its history retained, and the DataHub description is
corrected.

The loop is drawn as a diagram in
[the README](README.md#the-loop-the-investigate-skill-runs) — rendered there rather than inline
here, since Devpost's description field doesn't render Mermaid.

**Claude Code is the primary interface.** The memory layer ships as a Claude Code plugin with three slash commands — `/datahub-memory:investigate`, `/datahub-memory:recall`, `/datahub-memory:writeback` — over two MCP servers (delapan-backed memory, and `mcp-server-datahub`). The scripted CLI exists for a non-interactive, gated run; everything in the demo video is the plugin driving Claude Code. See the testing instructions below for the exact prompts.

## How we built it

- **Two MCP servers, one Claude Agent SDK loop.** `mcp-server-datahub` (stdio, OSS, `TOOLS_IS_MUTATION_ENABLED=true`) alongside delapan's tools exposed as in-process SDK tools (`memory_recall`, `memory_persist`, `check_freshness`, `writeback_description`, `writeback_report`). The agent loop and prompt policy (`datahub_memory/agent.py`, `prompts.py`) are the only new orchestration code — delapan's resolver, coverage banding, and provenance model are mature, shipped engine code we're consuming, not reimplementing.
- **Memory bridge** (`datahub_memory/bridge.py`) turns an agent conclusion into a delapan `Finding` whose `content` carries a JSON `grounded_in` block of `{urn, snapshot_hash}` pairs — `snapshot_hash` is a truncated SHA-256 over field paths/types and upstream URNs, computed at persistence and explicit re-verification.
- **Demo catalog** (`demo/seed.py`): a 4-dataset revenue chain (`raw_payments → stg_payments → fct_revenue → monthly_revenue`) with real lineage edges and one seeded incident, published purely via DataHub's Python emitter — no live warehouse behind it, deliberately (see "Design notes" in the README).
- **Drift** (`demo/drift.py`): renames a field in `stg_payments`, re-emitted through the same schema aspect the agent reads — a real metadata mutation, not a mock.
- **Claude Code plugin** (`.claude-plugin/`, `mcp.json`, `skills/`): the same agent packaged as `/datahub-memory:investigate`, `/datahub-memory:recall`, `/datahub-memory:writeback` skills, so the loop is usable interactively inside Claude Code, not just via the CLI.
- **Open upstream PR #62**: [`datahub-investigate`](https://github.com/datahub-project/datahub-skills/pull/62) generalizes the investigate → trace → persist → write-back pattern as a skill any agent can use against DataHub.
- **Open upstream PR #69**: [`datahub-memory`](https://github.com/datahub-project/datahub-skills/pull/69) proposes a vendor-neutral recall-first pattern using DataHub Documents as the catalog-native memory store. It is independent of #62; the two compose.

## Challenges we ran into

- **`mcp-server-datahub` v0.6.0 has no read tool for institutional memory.** We seeded the incident as `InstitutionalMemoryClass` first — the "correct" DataHub-native way to record it — and only discovered live, while building the investigation flow, that the MCP server exposes tools to *write* that aspect but nothing to *read* it back. An agent driven only by that MCP surface could never see an incident recorded that way, no matter how well it searched. Fix: publish the same incident a second time as a `save_document`-created Document, which *is* discoverable via `search_documents`/`grep_documents`. Both are seeded; only the Document is actually found by the agent today.
- **An asyncio event-loop collision, twice.** delapan's `recall`/`persist` calls each do their own internal `asyncio.run()` — fine standalone, but called directly from inside the Claude Agent SDK's own already-running event loop, that raises "asyncio.run() cannot be called from a running event loop." Worse, once dispatched to a thread pool, delapan's embedding/LLM clients cache a single `AsyncOpenAI` client bound to whichever event loop first constructed it — a *different* worker thread on a later call reusing that stale-loop-bound client intermittently breaks. Fix: route every delapan call through a single-worker `ThreadPoolExecutor` (serializing them onto one thread) and drop delapan's cached clients before each call, forcing a fresh client bound to that thread's fresh loop.
- **The resolver's op-label isn't always the word you expect.** delapan's resolver labels a retirement `UPDATE` (refinement) or `SUPERSEDE` (contradiction). In the canonical run, re-verifying a stale trust verdict produced `UPDATE`. Both use the same supersession path (`invalidated_at` set, old row retained, resolution event recorded), so the verification gate checks the state change rather than requiring one label.

## Accomplishments we're proud of

- A working knowledge-inheritance loop with real, measured before/after numbers — not a claimed speedup, a captured one (`demo/counters-baseline.json`, reproducible via `demo/run_demo.sh`).
- On-demand structural drift detection: `check_freshness` compares recorded hashes instead of asking an LLM to choose which entity to inspect.
- Versioned retirement proven on camera against a live DataHub instance and resolver call, with a runner that gates on database state (`resolution_events` delta + `invalidated_at` count) rather than trusting stdout.
- Ships two ways from one codebase — a plain CLI (`python -m datahub_memory "..."`) and a Claude Code plugin — with no logic duplicated between them.
- Two open upstream contribution PRs to DataHub's own skills repo, not just a submission that consumes DataHub.

## What's next

- Generalize `check_freshness` beyond schema+lineage hashing to also catch drift in institutional memory / description content itself, not just structural aspects.
- Glossary-term proposals through DataHub's human-in-the-loop approval surface (`add_terms`/`add_tags` are wired as available MCP tools but not yet exercised by the agent loop).
- Investigate why the resolver's `UPDATE`-vs-`SUPERSEDE` classification is inconsistent for what look like equivalent contradictions, and whether that's worth tightening in delapan itself.
- A multi-question demo KB (today's scenario is deliberately one question, three beats) to show coverage banding across a broader set of prior investigations.

---

## Testing instructions for judges

**Prerequisites:** Docker running, Python 3.11+, git, sqlite3, and [uv](https://docs.astral.sh/uv/) (required — both forms spawn `uvx mcp-server-datahub`).

**Shared setup — both paths need this:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
demo/quickstart.sh          # docker quickstart + token mint -> .env.local
source .env.local
python -m demo.seed         # seed the demo catalog + incident document
```

### Path A — Claude Code (the primary interface)

Claude Code **is** the agent: the plugin registers both MCP servers and the three skills, and your
Claude Code session drives the loop. A logged-in Claude Code session supplies the agent turns, so
this path does not separately require `ANTHROPIC_API_KEY`.

```bash
claude plugin marketplace add .
claude plugin install datahub-memory@datahub-memory
claude          # launch from the same shell where you sourced .env.local
```

The three beats from the video, as prompts you can paste:

| # | Prompt | What should happen |
|---|---|---|
| 1 | `/datahub-memory:investigate Can I trust monthly_revenue for the board report?` | Memory is `gap` → 16 total agent tool calls in the canonical run, including DataHub reads, memory persistence, and writes → description + report written back. ~2 min. Watch it land at http://localhost:9002. |
| 2 | `/clear`, then `/datahub-memory:recall Can I trust monthly_revenue for the board report?` | One `memory_recall`, **zero** DataHub calls, answer cites beat 1's finding ids and URNs. Seconds — the 16 → 1 comparison. |
| 3 | `python -m demo.drift` in another shell, then `/datahub-memory:investigate Can I trust monthly_revenue for the board report? (re-verify: upstream schema may have changed)` | The explicit staleness wording routes to `check_freshness`, which compares all four structural snapshots and names `stg_payments` as changed. The stale verdict is retired with history retained; stale documentation is corrected. |

Confirm the retirement straight from the store, no agent involved:

```bash
sqlite3 .data/delapan.db "SELECT op, COUNT(*) FROM resolution_events GROUP BY op;"
```

### Path B — scripted CLI (non-interactive)

```bash
demo/run_demo.sh            # all 3 beats, gates on version-retirement evidence
demo/run_demo.sh --verify-only   # re-check that gate after a full run
```

**Use the full runner only against the disposable quickstart catalog.** To create a clean baseline,
it clears prior editable descriptions and hard-deletes non-seed Documents found in the configured
DataHub instance.

**Token generation** is fully automated by `demo/quickstart.sh` — no manual DataHub UI steps required. It logs in as the quickstart's default `datahub`/`datahub` user, then mints a personal access token via GraphQL (`createAccessToken`). One quirk worth knowing if you watch it run: the very first attempt(s) right after `docker check` reports healthy typically 403 with "Unauthorized to perform this action," even for the root user — the bootstrap policy that grants token-generation privilege is indexed asynchronously and isn't queryable by the authorizer for roughly 30-60 seconds after GMS comes up healthy. This is expected, not a failure; `quickstart.sh` retries the mutation for up to 2 minutes before giving up. The resulting `DATAHUB_GMS_URL`/`DATAHUB_GMS_TOKEN` are written to `.env.local` automatically.

**Required keys beyond what `quickstart.sh` provides:**

| Variable | Path A (Claude Code) | Path B (CLI) |
|---|---|---|
| `AI_GATEWAY_API_KEY` | Required to reproduce the resolver-backed ADD / NOOP / UPDATE flow; it can also supply embeddings. `OPENAI_API_KEY` is an embeddings alternative, not a resolver-key replacement. | Required, same reason. |
| `ANTHROPIC_API_KEY` | Not needed when Claude Code is already logged in; that session supplies the model turns. | Required unless the local `claude` CLI is logged in; the Agent SDK drives the turns. |

Export them in the shell you launch `claude` from (Path A) or run `demo/run_demo.sh` from (Path B) — `mcp.json` passes them through to the MCP servers. See `.env.example`.

**Expected runtime:** the 3-beat scenario itself is ~4 minutes of live agent time (measured: 127.2s + 20.9s + 98.4s ≈ 4.1 min for beats 1-3 combined), plus first-time Docker image pulls for `docker quickstart` (5-15 minutes on a cold Docker cache, one-time). `demo/run_demo.sh --verify-only` re-checks the beat-3 retirement gate against whatever database a prior full run left behind, with zero new agent spend, in under a second — useful for re-verifying the claim without re-running the live scenario.

**What "pass" looks like:** `demo/run_demo.sh` prints a per-beat `resolution_events` delta, a live-vs-retired findings table after beat 3, and exits `0`. If beat 3 doesn't produce a version retirement (an `UPDATE` or `SUPERSEDE` event **and** an increase in rows with `findings.invalidated_at`), the script exits non-zero and names exactly which ops fired.

---

## Sample outputs

Judges are not required to run anything — [`examples/`](examples/README.md) holds real artifacts from real runs, verbatim, so the quality of what the agent produces can be assessed by reading:

| File | What it is |
|---|---|
| [`datahub-writebacks.md`](examples/datahub-writebacks.md) | **The artifacts written back into DataHub** — an agent-authored trust-review Document attached to all four datasets in the chain, and the `stg_payments` description. Each is shown as beat 1 wrote it *and* as beat 3 corrected it after the schema drift, read back out of the live catalog via GMS aspect reads. This is the "contribute back to the graph" half of the loop, in full. |
| [`investigation-answer.md`](examples/investigation-answer.md) | The agent's own answers for beat 1 and beat 3, plus the full finding content persisted for each, with `grounded_in` URNs and snapshot hashes. |
| [`resolution-log.md`](examples/resolution-log.md) | The `resolution_events` rows and per-beat ADD/UPDATE/NOOP deltas the write-time resolver produced. |
| [`verify-only-output.md`](examples/verify-only-output.md) | Captured output from the runner's version-retirement gate, read straight from SQLite. A fresh clone must run the full scenario before invoking `--verify-only` itself. |

The write-backs come from the run captured in the demo video, so what the video shows landing on screen at 0:50 and 2:00 can be read here in full.

---

## Video (final cut — 2:31, split-screen, caption-driven)

Full storyline and verbatim caption script: [`docs/video-script.md`](docs/video-script.md).

**https://youtu.be/d-R0-WuPzXw**

Composed agentically as a Remotion composition, and **split-screen throughout the
two agent beats**: on the left the *real interactive Claude Code TUI* (hosted in
tmux, captured with `asciinema` and rendered with `agg`, so the `/datahub-memory:`
autocomplete popup and every `Called plugin:…` / `Skill(…)` block is Claude Code's
own rendering, not a reconstruction); on the right the live DataHub page, recorded
by a Playwright browser reloading every ~3s so server-side changes become visible
as they land. Both panes were recorded in the **same wall-clock window** and are
composited against a measured offset (`split3/sync.json`), so cause and effect on
screen are genuine rather than edited together.

Footage is speed-ramped to keep the runtime under 3 minutes, with **1× real-time
brackets held over the causal moments** — the write-back landing in Beat A, and
`check_freshness` plus the correction landing in Beat B. Silent by design and fully
legible sound-off; the captions below double as a voice-over script if dubbed later.

| Scene | Time | Screen | Caption |
|---|---|---|---|
| S1 | 0:00 | Black + kinetic hook | "Someone already answered this." / "You just don't know it." |
| Tagline | 0:05 | Black | "**datahub-memory** — a memory layer for DataHub. Five tools, so an answer has somewhere to live." |
| Autocomplete | 0:08 | Real TUI, `/datahub-memory:` popup building up | "Three skills call those tools. This one **investigates.**" |
| Beat A | 0:12 | **Split:** TUI investigating ‖ `stg_payments` Documentation tab | "Memory is empty — so it **goes and earns the answer:** lineage, schemas, documents." |
| ↳ | 0:46 | caption in, pane still reads "No documentation yet" | "**writeback** puts it in the catalog — watch the description appear." |
| ↳ | 0:50 | **1× real time:** `Skill(datahub-memory:writeback)` left, description appearing right | cause and effect in one wall-clock window |
| Inherit | 0:58 | Beat-2 terminal + animated 16→1 / 127s→21s counter | "Same question, new session. **memory_recall** answers it — 1 call instead of 16, read from the database." |
| Drift still | 1:12 | Drifted schema still | "Upstream, **a column was renamed.**" |
| Beat B | 1:15 | **Split:** TUI re-verifying ‖ same Documentation tab | "Memory that never updates is just **amnesia with better branding.**" |
| ↳ | ~1:40 | **1×:** `check_freshness` naming the drifted entity | "**check_freshness** re-hashes every grounded entity and names the one that moved." |
| ↳ | 2:00 | **1×:** corrected description lands in DataHub | "The stale answer is **corrected** — nothing deleted, everything dated." |
| Gate | 2:05 | `--verify-only` gate output | "The gate reads resolution events **straight from SQLite.** Every number in the repo traces to this run." |
| End card | 2:13 | End card | the layer · its five tools · 16× fewer tool calls · the three skills · repo + PRs #62 and #69 |
