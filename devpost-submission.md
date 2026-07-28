# Devpost submission text — datahub-memory

Ready-to-paste copy for the Devpost submission form. **Build with DataHub: The Agent Hackathon**, Challenge 1 ("Agents That Do Real Work").

---

## Inspiration

Every data team re-derives the same answers. Someone investigates whether `monthly_revenue` can be trusted, traces the incident that touched it, checks the schema — and a month later, a different person (or agent) asks the exact same question and starts from zero, because the investigation lived in a Slack thread or a person's head, not in the catalog. DataHub already models the connective tissue (lineage, schema, institutional memory) that makes an investigation possible; what's missing is a place for the *conclusions* to live, grounded enough to trust and fresh enough to act on. Challenge 1's own framing — agents that read metadata, take action, and write results back so knowledge inherits across users and agents — is exactly this gap.

We had a memory engine already built for this shape of problem: [delapan](https://github.com/anthonysuherli/delapan-be), an AGPL-3.0 engine (entrant-owned) with a write-time resolver that decides, per new conclusion, whether it's genuinely new or a refinement/contradiction of something already known — never appending duplicates, never silently overwriting. Pairing it with DataHub's MCP surface was the natural next step: ground every finding in real URNs, and let the catalog itself carry what was learned.

## What it does

`datahub-memory` is an agent that:

1. **Investigates** — given a question like "Can I trust `monthly_revenue` for the board report?", it walks DataHub via MCP (search → lineage → schema → institutional memory) and forms a grounded conclusion.
2. **Remembers** — every conclusion is persisted as a delapan finding whose `grounded_in` field carries the exact DataHub URNs (plus a schema+lineage hash) it was derived from. delapan's write-time resolver decides ADD / UPDATE / NOOP / SUPERSEDE against everything already known — memory that dedups and self-corrects at write time, not read time.
3. **Answers instantly the second time** — a related question routes to memory first. If coverage is `rich` or `sparse`, it answers directly from the finding, citing URNs, with zero new DataHub calls.
4. **Knows when memory has gone stale** — if the question itself hints at possible drift ("re-verify", "has this changed"), a deterministic `check_freshness` tool re-hashes every grounded entity's *current* schema and lineage and diffs it against what was recorded. No guessing which entity might have moved — it checks all of them and reports exactly which ones did.
5. **Writes back** — descriptions and reports go straight into DataHub (`update_description`, `save_document`, DataHub's own MCP mutation tools), so the next investigator — human or agent — inherits the answer from the catalog itself, not just from this tool's private memory.

Measured on a live 3-beat run: the second time the same question is asked, the agent needs 1 tool call and ~21 seconds instead of 14 tool calls and ~102 seconds. When the upstream schema drifts between asks, the same deterministic mechanism that answers instantly from memory is the one that catches the drift and forces a targeted re-investigation — the stale finding is retired bi-temporally (never deleted), and a corrected one takes its place.

## How we built it

- **Two MCP servers, one Claude Agent SDK loop.** `mcp-server-datahub` (stdio, OSS, `TOOLS_IS_MUTATION_ENABLED=true`) alongside delapan's tools exposed as in-process SDK tools (`memory_recall`, `memory_persist`, `check_freshness`, `writeback_description`, `writeback_report`). The agent loop and prompt policy (`datahub_memory/agent.py`, `prompts.py`) are the only new orchestration code — delapan's resolver, coverage banding, and provenance model are mature, shipped engine code we're consuming, not reimplementing.
- **Memory bridge** (`datahub_memory/bridge.py`) turns an agent conclusion into a delapan `Finding` whose `content` carries a JSON `grounded_in` block of `{urn, snapshot_hash}` pairs — `snapshot_hash` is a SHA-256 over the entity's schema fields and lineage upstreams, computed identically at write time (in `memory_persist`) and read time (in `check_freshness`).
- **Demo catalog** (`demo/seed.py`): a 4-dataset revenue chain (`raw_payments → stg_payments → fct_revenue → monthly_revenue`) with real lineage edges and one seeded incident, published purely via DataHub's Python emitter — no live warehouse behind it, deliberately (see "Design notes" in the README).
- **Drift** (`demo/drift.py`): renames a field in `stg_payments`, re-emitted through the same schema aspect the agent reads — a real metadata mutation, not a mock.
- **Claude Code plugin** (`.claude-plugin/`, `mcp.json`, `skills/`): the same agent packaged as `/datahub-memory:investigate`, `/datahub-memory:recall`, `/datahub-memory:writeback` skills, so the loop is usable interactively inside Claude Code, not just via the CLI.
- **Upstream contribution**: [`datahub-project/datahub-skills#62`](https://github.com/datahub-project/datahub-skills/pull/62) generalizes the investigate → trace → persist → write-back pattern as a skill any agent (not just this one) can use against DataHub.

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

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
demo/quickstart.sh          # docker quickstart + token mint -> .env.local
source .env.local
python -m demo.seed         # seed the demo catalog + incident document
demo/run_demo.sh            # all 3 beats, gates on bi-temporal retirement evidence
```

**Token generation** is fully automated by `demo/quickstart.sh` — no manual DataHub UI steps required. It logs in as the quickstart's default `datahub`/`datahub` user, then mints a personal access token via GraphQL (`createAccessToken`). One quirk worth knowing if you watch it run: the very first attempt(s) right after `docker check` reports healthy typically 403 with "Unauthorized to perform this action," even for the root user — the bootstrap policy that grants token-generation privilege is indexed asynchronously and isn't queryable by the authorizer for roughly 30-60 seconds after GMS comes up healthy. This is expected, not a failure; `quickstart.sh` retries the mutation for up to 2 minutes before giving up. The resulting `DATAHUB_GMS_URL`/`DATAHUB_GMS_TOKEN` are written to `.env.local` automatically.

**Required keys beyond what `quickstart.sh` provides:**

| Variable | Why |
|---|---|
| `AI_GATEWAY_API_KEY` **or** `OPENAI_API_KEY` | delapan's embedding/LLM calls (`memory_recall`/`memory_persist`) fail without one of these. |
| Claude Code login, **or** `ANTHROPIC_API_KEY` | The agent loop runs on the Claude Agent SDK, which drives the actual investigation turns. |

Both must be present in the environment before `demo/run_demo.sh` (or `python -m datahub_memory "..."`) runs — see `.env.example`.

**Expected runtime:** the 3-beat scenario itself is ~5 minutes of live agent time (measured: 102.3s + 21.2s + 159.7s ≈ 4.7 min for beats 1-3 combined), plus first-time Docker image pulls for `docker quickstart` (5-15 minutes on a cold Docker cache, one-time). `demo/run_demo.sh --verify-only` re-checks the beat-3 retirement gate against whatever database a prior full run left behind, with zero new agent spend, in under a second — useful for re-verifying the claim without re-running the live scenario.

**What "pass" looks like:** `demo/run_demo.sh` prints a per-beat `resolution_events` delta, a live-vs-retired findings table after beat 3, and exits `0`. If beat 3 doesn't produce a bi-temporal retirement (a `resolution_events` delta containing `UPDATE` or `SUPERSEDE`, **and** the `findings.invalidated_at` count actually increasing), the script exits non-zero and names exactly which ops did fire instead — it does not silently pass on a partial result.

---

## Video script (<3 min, beat-by-beat shot list)

Recorded from `demo/run_demo.sh`'s real terminal output (`terminal-demo-video` skill) intercut with the DataHub UI. Total budget: ~2:50.

| Time | Shot | Narration |
|---|---|---|
| 0:00–0:12 | Title card: "datahub-memory — grounded institutional memory for data teams." Cut to DataHub UI, `stg_payments` dataset page, **Documentation** tab showing an **empty description**. | "Every data team re-investigates the same questions. Here's a dataset with no description at all — and no memory of what anyone's already learned about it." |
| 0:12–0:40 | Terminal: `demo/run_demo.sh` starts. Show `=== BEAT 1: investigate ===` scrolling, then the final printed answer + counters line (`{"turns": 15, "tool_calls": 14, "duration_s": 102.3}`). | "We ask: can I trust `monthly_revenue` for the board report? The agent has no memory yet, so it does the real work — walks DataHub's lineage, reads institutional memory on every upstream entity, and finds a resolved incident four hops back. Fourteen tool calls, about a minute and a half." |
| 0:40–0:58 | Cut to DataHub UI: `stg_payments` **Documentation** tab now **filled** (post-write-back). Then the DataHub Documents view showing the agent's saved investigation report. | "And it doesn't just answer — it writes back. The description gets filled in directly on the dataset, and the full investigation is saved as a document attached to the entity, so the next person who opens this page inherits the answer." |
| 0:58–1:10 | DataHub UI: open the seeded incident document ("INCIDENT 2026-07-24: Stripe webhook outage — late backfill"). | "The incident itself — a six-hour Stripe webhook outage — was already recorded in DataHub as a document. The agent found it by searching, the same way any teammate would." |
| 1:10–1:35 | Terminal: `=== BEAT 2: inherit ===`, same question, fresh session. Show the near-instant output and counters (`{"turns": 2, "tool_calls": 1, "duration_s": 21.2}`). Split-screen or side-by-side counters: 14 calls/102s vs. 1 call/21s. | "Now we ask the exact same question, in a brand-new session. One tool call — a memory lookup, nothing else — and it answers in twenty-one seconds, citing the same finding and the same URNs. No re-investigation needed." |
| 1:35–1:50 | Terminal: `python -m demo.drift` output (`drift emitted`). Cut to DataHub UI: `stg_payments` schema tab, field `amount_usd` → `amount`. | "Now the upstream schema actually changes — a field gets renamed. Nothing tells the agent this happened. Its memory still thinks the old schema is current." |
| 1:50–2:25 | Terminal: `=== BEAT 3: re-verify ===`, worded to signal possible staleness. Show the `check_freshness` reasoning surface in the answer text ("Schema drift detected in `stg_payments`...") and the final counters (`{"turns": 16, "tool_calls": 15, "duration_s": 159.7}`). | "We ask again, this time flagging that things might have changed. The agent doesn't guess — it deterministically re-hashes every entity it's grounded in against DataHub's current state, and it correctly flags `stg_payments`, the one that actually moved. That triggers a real re-investigation." |
| 2:25–2:45 | Terminal: the `resolution_events` delta printout (`ADD: +1`, `UPDATE: +1`) and the live-vs-retired findings table from the runner's output. | "The result: a new finding documents the drift, and the old trust verdict is retired — not deleted, just marked stale, with a permanent record of why. This is bi-temporal memory: nothing disappears, but the agent, and anyone downstream of it, never acts on stale information again." |
| 2:45–2:50 | End card: the three-beat counters table + "Claude Code plugin: `/datahub-memory:*`" + PR link (`datahub-project/datahub-skills#62`). | "datahub-memory: investigate once, inherit forever, and know the moment it's wrong." |
