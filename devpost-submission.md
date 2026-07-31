# Devpost submission text — datahub-memory

Ready-to-paste copy for the Devpost submission form. **Build with DataHub: The Agent Hackathon**, Challenge 1 ("Agents That Do Real Work").

## Devpost form fields

- **Title**: `datahub-memory`
- **Tagline** (one line, ≤120 chars): Institutional memory for data teams: investigate once, inherit forever — and know the moment it's wrong
- **Elevator pitch** (reused as the first two paragraphs of the Story below, and as the README hero paragraphs):

  datahub-memory is a DataHub investigation agent with grounded, self-correcting memory. It reads DataHub entirely through `mcp-server-datahub`'s own tools — search, lineage, schema, and document reads — and writes what it learns back through DataHub's own mutation tools (`update_description`, `save_document`), so the catalog itself inherits the answer, not just the agent's private memory. Every conclusion is persisted as a delapan finding `grounded_in` the exact DataHub URNs it was derived from, and deterministically re-verified — by re-hashing those entities' current schema and lineage, never by guessing — the moment the world underneath it changes.

  Measured live against a docker-quickstart DataHub v1.5.0.6 + `mcp-server-datahub` v0.6.0 (`demo/counters-baseline.json`): investigating a trust question the first time costs 16 tool calls and 127s; asking the identical question again in a fresh session answers from memory in 1 tool call and 21s. The same pattern is contributed upstream as two DataHub multi-agent skills: [datahub-project/datahub-skills#62](https://github.com/datahub-project/datahub-skills/pull/62) (`datahub-investigate` — the deep-dive) and [#69](https://github.com/datahub-project/datahub-skills/pull/69) (`datahub-memory` — recall-first with documents as the catalog-native memory store).

---

## Inspiration

datahub-memory is a DataHub investigation agent with grounded, self-correcting memory. It reads DataHub entirely through `mcp-server-datahub`'s own tools — search, lineage, schema, and document reads — and writes what it learns back through DataHub's own mutation tools (`update_description`, `save_document`), so the catalog itself inherits the answer, not just the agent's private memory. Every conclusion is persisted as a delapan finding `grounded_in` the exact DataHub URNs it was derived from, and deterministically re-verified — by re-hashing those entities' current schema and lineage, never by guessing — the moment the world underneath it changes.

Measured live against a docker-quickstart DataHub v1.5.0.6 + `mcp-server-datahub` v0.6.0 (`demo/counters-baseline.json`): investigating a trust question the first time costs 16 tool calls and 127s; asking the identical question again in a fresh session answers from memory in 1 tool call and 21s. The same pattern is contributed upstream as two DataHub multi-agent skills: [datahub-project/datahub-skills#62](https://github.com/datahub-project/datahub-skills/pull/62) (`datahub-investigate` — the deep-dive) and [#69](https://github.com/datahub-project/datahub-skills/pull/69) (`datahub-memory` — recall-first with documents as the catalog-native memory store).

Every data team re-derives the same answers. Someone investigates whether `monthly_revenue` can be trusted, traces the incident that touched it, checks the schema — and a month later, a different person (or agent) asks the exact same question and starts from zero, because the investigation lived in a Slack thread or a person's head, not in the catalog. DataHub already models the connective tissue (lineage, schema, institutional memory) that makes an investigation possible; what's missing is a place for the *conclusions* to live, grounded enough to trust and fresh enough to act on. Challenge 1's own framing — agents that read metadata, take action, and write results back so knowledge inherits across users and agents — is exactly this gap.

We had a memory engine already built for this shape of problem: [delapan](https://github.com/anthonysuherli/delapan), an AGPL-3.0 engine (entrant-owned) with a write-time resolver that decides, per new conclusion, whether it's genuinely new or a refinement/contradiction of something already known — never appending duplicates, never silently overwriting. Pairing it with DataHub's MCP surface was the natural next step: ground every finding in real URNs, and let the catalog itself carry what was learned.

## What it does

`datahub-memory` is an agent that:

1. **Investigates** — given a question like "Can I trust `monthly_revenue` for the board report?", it walks DataHub via MCP (search → lineage → schema → institutional memory) and forms a grounded conclusion.
2. **Remembers** — every conclusion is persisted as a delapan finding whose `grounded_in` field carries the exact DataHub URNs (plus a schema+lineage hash) it was derived from. delapan's write-time resolver decides ADD / UPDATE / NOOP / SUPERSEDE against everything already known — memory that dedups and self-corrects at write time, not read time.
3. **Answers instantly the second time** — a related question routes to memory first. If coverage is `rich` or `sparse`, it answers directly from the finding, citing URNs, with zero new DataHub calls.
4. **Knows when memory has gone stale** — if the question itself hints at possible drift ("re-verify", "has this changed"), a deterministic `check_freshness` tool re-hashes every grounded entity's *current* schema and lineage and diffs it against what was recorded. No guessing which entity might have moved — it checks all of them and reports exactly which ones did.
5. **Writes back** — descriptions and reports go straight into DataHub (`update_description`, `save_document`, DataHub's own MCP mutation tools), so the next investigator — human or agent — inherits the answer from the catalog itself, not just from this tool's private memory.

Measured on a live 3-beat run: the second time the same question is asked, the agent needs 1 tool call and ~21 seconds instead of 16 tool calls and ~127 seconds. When the upstream schema drifts between asks, the same deterministic mechanism that answers instantly from memory is the one that catches the drift and forces a targeted re-investigation — the stale finding is retired bi-temporally (never deleted), and a corrected one takes its place.

The loop is drawn as a diagram in [the README](README.md#the-loop) — rendered there rather than inline here, since Devpost's description field doesn't render Mermaid.

**Claude Code is the primary interface.** It ships as a Claude Code plugin with three slash commands — `/datahub-memory:investigate`, `/datahub-memory:recall`, `/datahub-memory:writeback` — over two MCP servers (delapan-backed memory, and `mcp-server-datahub`). The scripted CLI exists for a non-interactive, gated run; everything in the demo video is the plugin driving Claude Code. See the testing instructions below for the exact prompts.

## How we built it

- **Two MCP servers, one Claude Agent SDK loop.** `mcp-server-datahub` (stdio, OSS, `TOOLS_IS_MUTATION_ENABLED=true`) alongside delapan's tools exposed as in-process SDK tools (`memory_recall`, `memory_persist`, `check_freshness`, `writeback_description`, `writeback_report`). The agent loop and prompt policy (`datahub_memory/agent.py`, `prompts.py`) are the only new orchestration code — delapan's resolver, coverage banding, and provenance model are mature, shipped engine code we're consuming, not reimplementing.
- **Memory bridge** (`datahub_memory/bridge.py`) turns an agent conclusion into a delapan `Finding` whose `content` carries a JSON `grounded_in` block of `{urn, snapshot_hash}` pairs — `snapshot_hash` is a SHA-256 over the entity's schema fields and lineage upstreams, computed identically at write time (in `memory_persist`) and read time (in `check_freshness`).
- **Demo catalog** (`demo/seed.py`): a 4-dataset revenue chain (`raw_payments → stg_payments → fct_revenue → monthly_revenue`) with real lineage edges and one seeded incident, published purely via DataHub's Python emitter — no live warehouse behind it, deliberately (see "Design notes" in the README).
- **Drift** (`demo/drift.py`): renames a field in `stg_payments`, re-emitted through the same schema aspect the agent reads — a real metadata mutation, not a mock.
- **Claude Code plugin** (`.claude-plugin/`, `mcp.json`, `skills/`): the same agent packaged as `/datahub-memory:investigate`, `/datahub-memory:recall`, `/datahub-memory:writeback` skills, so the loop is usable interactively inside Claude Code, not just via the CLI.
- **Upstream contribution**: [`datahub-project/datahub-skills#62`](https://github.com/datahub-project/datahub-skills/pull/62) generalizes the investigate → trace → persist → write-back pattern as a skill any agent (not just this one) can use against DataHub.
- **Second upstream contribution**: [`datahub-project/datahub-skills#69`](https://github.com/datahub-project/datahub-skills/pull/69) contributes `datahub-memory` — the recall-first half of this project, vendor-neutral, using DataHub documents as the memory store (recall → investigate only the gap → persist → supersede, never delete). Independent of #62; the two compose.

## Challenges we ran into

- **`mcp-server-datahub` v0.6.0 has no read tool for institutional memory.** We seeded the incident as `InstitutionalMemoryClass` first — the "correct" DataHub-native way to record it — and only discovered live, while building the investigation flow, that the MCP server exposes tools to *write* that aspect but nothing to *read* it back. An agent driven only by that MCP surface could never see an incident recorded that way, no matter how well it searched. Fix: publish the same incident a second time as a `save_document`-created Document, which *is* discoverable via `search_documents`/`grep_documents`. Both are seeded; only the Document is actually found by the agent today.
- **An asyncio event-loop collision, twice.** delapan's `recall`/`persist` calls each do their own internal `asyncio.run()` — fine standalone, but called directly from inside the Claude Agent SDK's own already-running event loop, that raises "asyncio.run() cannot be called from a running event loop." Worse, once dispatched to a thread pool, delapan's embedding/LLM clients cache a single `AsyncOpenAI` client bound to whichever event loop first constructed it — a *different* worker thread on a later call reusing that stale-loop-bound client intermittently breaks. Fix: route every delapan call through a single-worker `ThreadPoolExecutor` (serializing them onto one thread) and drop delapan's cached clients before each call, forcing a fresh client bound to that thread's fresh loop.
- **The resolver's op-label isn't always the word you expect.** delapan's write-time resolver labels a retirement `UPDATE` (refinement) or `SUPERSEDE` (outright contradiction) based on its own judgment of the relationship between the old and new finding — and in our canonical run, a schema-drift-triggered retirement that reads to a human as a contradiction ("the old trust verdict is now stale") got classified `UPDATE`, not `SUPERSEDE`. Both route through the identical `store.supersede_finding` code path and produce the identical bi-temporal effect (`invalidated_at` set, nothing deleted, a `resolution_events` row recorded) — the op label is a classification nuance, not a different mechanism. We rewrote our own demo-verification gate to be agnostic to which label fires, checking for the retirement itself rather than one specific word.

## Accomplishments we're proud of

- A working knowledge-inheritance loop with real, measured before/after numbers — not a claimed speedup, a captured one (`demo/counters-baseline.json`, reproducible via `demo/run_demo.sh`).
- Deterministic drift detection: `check_freshness` is a hash comparison, not an LLM guessing which entity might have changed — it can't be wrong about *which* entity drifted, only about narrating *what* the drift means.
- Bi-temporal retirement proven on camera against a live DataHub instance and a live resolver call, with a runner that gates on the actual database state (`resolution_events` delta + `invalidated_at` count) rather than trusting stdout.
- Ships two ways from one codebase — a plain CLI (`python -m datahub_memory "..."`) and a Claude Code plugin — with no logic duplicated between them.
- An upstream contribution back to DataHub's own skills repo, not just a submission that consumes DataHub.

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

Claude Code **is** the agent: the plugin registers both MCP servers and the three skills, and your Claude Code session drives the loop. Nothing further to authenticate — no `ANTHROPIC_API_KEY`, no Agent SDK runner.

```bash
claude plugin marketplace add .
claude plugin install datahub-memory@datahub-memory
claude          # launch from the same shell where you sourced .env.local
```

The three beats from the video, as prompts you can paste:

| # | Prompt | What should happen |
|---|---|---|
| 1 | `/datahub-memory:investigate Can I trust monthly_revenue for the board report?` | Memory is `gap` → ~16 DataHub tool calls → 3-4 findings persisted → description + report document written back to `stg_payments`. ~2 min. Watch it land at http://localhost:9002. |
| 2 | `/clear`, then `/datahub-memory:recall Can I trust monthly_revenue for the board report?` | One `memory_recall`, **zero** DataHub calls, answer cites beat 1's finding ids and URNs. Seconds — the 16 → 1 comparison. |
| 3 | `python -m demo.drift` in another shell, then `/datahub-memory:investigate Can I trust monthly_revenue for the board report? (re-verify: upstream schema may have changed)` | The staleness wording routes to `check_freshness`, which re-hashes all four grounded entities and names `stg_payments` — not the lineage root — as the one that moved. Stale verdict retired bi-temporally; wrong description corrected. |

Confirm the retirement straight from the store, no agent involved:

```bash
sqlite3 .data/delapan.db "SELECT op, COUNT(*) FROM resolution_events GROUP BY op;"
```

### Path B — scripted CLI (non-interactive)

```bash
demo/run_demo.sh            # all 3 beats, gates on bi-temporal retirement evidence
demo/run_demo.sh --verify-only   # re-check that gate after a full run
```

**Token generation** is fully automated by `demo/quickstart.sh` — no manual DataHub UI steps required. It logs in as the quickstart's default `datahub`/`datahub` user, then mints a personal access token via GraphQL (`createAccessToken`). One quirk worth knowing if you watch it run: the very first attempt(s) right after `docker check` reports healthy typically 403 with "Unauthorized to perform this action," even for the root user — the bootstrap policy that grants token-generation privilege is indexed asynchronously and isn't queryable by the authorizer for roughly 30-60 seconds after GMS comes up healthy. This is expected, not a failure; `quickstart.sh` retries the mutation for up to 2 minutes before giving up. The resulting `DATAHUB_GMS_URL`/`DATAHUB_GMS_TOKEN` are written to `.env.local` automatically.

**Required keys beyond what `quickstart.sh` provides:**

| Variable | Path A (Claude Code) | Path B (CLI) |
|---|---|---|
| `AI_GATEWAY_API_KEY` **or** `OPENAI_API_KEY` | Required — delapan's embedding/LLM calls (`memory_recall`/`memory_persist`) fail without one. | Required, same reason. |
| Claude Code login, **or** `ANTHROPIC_API_KEY` | **Not needed** — you are already in Claude Code, which supplies the model turns. | Required — the Agent SDK drives the turns itself. |

Export them in the shell you launch `claude` from (Path A) or run `demo/run_demo.sh` from (Path B) — `mcp.json` passes them through to the MCP servers. See `.env.example`.

**Expected runtime:** the 3-beat scenario itself is ~4 minutes of live agent time (measured: 127.2s + 20.9s + 98.4s ≈ 4.1 min for beats 1-3 combined), plus first-time Docker image pulls for `docker quickstart` (5-15 minutes on a cold Docker cache, one-time). `demo/run_demo.sh --verify-only` re-checks the beat-3 retirement gate against whatever database a prior full run left behind, with zero new agent spend, in under a second — useful for re-verifying the claim without re-running the live scenario.

**What "pass" looks like:** `demo/run_demo.sh` prints a per-beat `resolution_events` delta, a live-vs-retired findings table after beat 3, and exits `0`. If beat 3 doesn't produce a bi-temporal retirement (a `resolution_events` delta containing `UPDATE` or `SUPERSEDE`, **and** the `findings.invalidated_at` count actually increasing), the script exits non-zero and names exactly which ops did fire instead — it does not silently pass on a partial result.

---

## Sample outputs

Judges are not required to run anything — [`examples/`](examples/README.md) holds real artifacts from real runs, verbatim, so the quality of what the agent produces can be assessed by reading:

| File | What it is |
|---|---|
| [`datahub-writebacks.md`](examples/datahub-writebacks.md) | **The artifacts written back into DataHub** — an agent-authored trust-review Document attached to all four datasets in the chain, and the `stg_payments` description. Each is shown as beat 1 wrote it *and* as beat 3 corrected it after the schema drift, read back out of the live catalog via GMS aspect reads. This is the "contribute back to the graph" half of the loop, in full. |
| [`investigation-answer.md`](examples/investigation-answer.md) | The agent's own answers for beat 1 and beat 3, plus the full finding content persisted for each, with `grounded_in` URNs and snapshot hashes. |
| [`resolution-log.md`](examples/resolution-log.md) | The `resolution_events` rows and per-beat ADD/UPDATE/NOOP deltas the write-time resolver produced. |
| [`verify-only-output.md`](examples/verify-only-output.md) | `demo/run_demo.sh --verify-only` re-checking the bi-temporal-retirement gate straight against SQLite. |

The write-backs come from the run captured in the demo video, so what the video shows landing on screen at 0:50 and 2:00 can be read here in full.

---

## Video (final cut — 2:31, split-screen, caption-driven)

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

| Scene | Time | Screen | Caption / story job |
|---|---|---|---|
| S1 | 0:00 | Black + kinetic hook | "Someone already answered this." / "You just don't know it." → "a Claude Code plugin that remembers what your data team already learned" |
| Autocomplete | 0:08 | Real TUI, `/datahub-memory:` popup building up | This ships as a Claude Code plugin — the commands are real |
| Beat A | 0:12 | **Split:** TUI investigating ‖ `stg_payments` Documentation tab | No memory yet: lineage → schemas → documents → the incident four hops upstream |
| ↳ | 0:46 | caption in, pane still reads "No documentation yet" | "It **writes the answer back** — watch the description appear" |
| ↳ | 0:50 | **1× real time:** `Skill(datahub-memory:writeback)` on the left, the description appearing on the right | The catalog itself inherits the answer — cause and effect in one wall-clock window |
| Inherit | 0:58 | Beat-2 terminal + animated 16→1 / 127s→21s counter | Same question, new session, answered from memory — numbers read from the database, not the transcript |
| Drift still | 1:12 | Drifted schema still | "Upstream, a column was renamed" (applied before recording — see the honesty note) |
| Beat B | 1:15 | **Split:** TUI re-verifying ‖ same Documentation tab | **1×:** the staleness signal routes to `check_freshness`, which re-hashes every grounded entity and reports "Drift confirmed: `stg_payments` has changed" |
| ↳ | 1:24 | | "Memory that never updates is just amnesia with better branding" |
| ↳ | 2:00 | **1×:** corrected description lands in DataHub | "⚠️ Column renamed, units now unasserted (detected 2026-07-29)" — the stale answer corrected, nothing deleted, everything dated |
| Gate | 2:05 | `--verify-only` gate output | The gate reads resolution events straight from SQLite — every number traces to this run |
| End card | 2:13 | End card | investigate once · inherit forever · know the moment it's wrong + plugin + repo + PRs #62 and #69 |
