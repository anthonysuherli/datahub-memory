# Devpost submission text — datahub-memory

Ready-to-paste copy for the Devpost submission form. **Build with DataHub: The Agent Hackathon**, Challenge 1 ("Agents That Do Real Work").

---

## Inspiration

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

**Expected runtime:** the 3-beat scenario itself is ~4 minutes of live agent time (measured: 127.2s + 20.9s + 98.4s ≈ 4.1 min for beats 1-3 combined), plus first-time Docker image pulls for `docker quickstart` (5-15 minutes on a cold Docker cache, one-time). `demo/run_demo.sh --verify-only` re-checks the beat-3 retirement gate against whatever database a prior full run left behind, with zero new agent spend, in under a second — useful for re-verifying the claim without re-running the live scenario.

**What "pass" looks like:** `demo/run_demo.sh` prints a per-beat `resolution_events` delta, a live-vs-retired findings table after beat 3, and exits `0`. If beat 3 doesn't produce a bi-temporal retirement (a `resolution_events` delta containing `UPDATE` or `SUPERSEDE`, **and** the `findings.invalidated_at` count actually increasing), the script exits non-zero and names exactly which ops did fire instead — it does not silently pass on a partial result.

---

## Video (final cut — 2:46, caption-driven)

Composed agentically: the real `demo/run_demo.sh` terminal recording (re-rendered
from the asciinema cast, no idle-capping) + live DataHub UI captures, assembled as
a Remotion composition — kinetic captions (the video is fully legible sound-off),
Ken Burns on UI stills, an animated 16→1 tool-call comparison, and an end card.
Silent by design; narration below doubles as a voice-over script if dubbed later.

| Scene | Time | Screen | Caption / story job |
|---|---|---|---|
| S1 | 0:00 | Black + kinetic hook | "Someone already answered this." / "You just don't know it." |
| S2 | 0:05 | stg_payments, empty description (Ken Burns) | A dataset feeding the board's revenue number — no record of what anyone learned |
| S3 | 0:12 | Beat-1 terminal (sped), hold on verdict | No memory yet: lineage → schemas → documents → incident four hops upstream. 16 tool calls · 127 s · cited verdict |
| S4 | 0:48 | Stills: description filled → report doc → incident doc | The knowledge now lives where the next person will look |
| S5 | 1:08 | Beat-2 terminal + animated 16→1 / 127s→21s comparison | Same question, new session, answered from memory — numbers read from the database, not the transcript |
| S6 | 1:32 | Drifted schema still | "Memory that never updates is just amnesia with better branding" |
| S7 | 1:42 | Beat-3 terminal, hold on retirement line | Re-hashes every grounded entity, flags exactly the table that moved, retires the stale verdict bi-temporally |
| S8 | 2:14 | `--verify-only` gate output | The gate reads resolution events straight from SQLite — every number traces to this run |
| S9 | 2:26 | End card | investigate once · inherit forever · know the moment it's wrong + plugin + repo + PR #62 |
