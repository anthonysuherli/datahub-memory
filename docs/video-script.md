# Demo video — storyline and caption script

The shipping cut is 2:31, silent, caption-driven, split-screen. This file is the
source of truth for what it argues and the exact caption text; the Remotion
composition is generated from it by hand (see the submission bundle's
`video-source-src/`).

## What changed in this revision

The first cut sold **datahub-memory as an investigation agent**. That inverts the
architecture: `datahub_memory/mcp_stub.py` exists to expose *five tools*, and the
investigation agent is one of three skills consuming them. The footage was already
correct — the terminal shows `/datahub-memory:investigate` doing exactly what it
does — so nothing was re-recorded. Only the captions and cards changed, to argue
the layer instead of the agent.

## Storyline

The spine is a single question asked three times, and what the catalog has learned
between each ask.

| Beat | Time | The argument |
|---|---|---|
| **Hook** | 0:00 | Someone on your team already answered this. The answer died in a Slack thread. |
| **The claim** | 0:05 | DataHub models lineage, schema, incidents — but has nowhere for a *conclusion* to live. datahub-memory is that place: five tools. |
| **The consumer** | 0:08 | Three skills call those tools. The one you're about to watch investigates. |
| **Earning it** | 0:12 | Memory is empty, so the skill pays full price: search → lineage → schemas → documents, and finds an incident four hops upstream. |
| **Putting it back** | 0:46 | The write-back tools push the conclusion into DataHub itself. The description fills on camera while the tool call is still on screen. |
| **Inheriting it** | 0:58 | Same question, new session. `memory_recall` answers it: 1 call instead of 16. The number is read from the database, not the transcript. |
| **The catch** | 1:12 | A column is renamed upstream. Memory that never updates is just amnesia with better branding. |
| **Catching it** | 1:15 | `check_freshness` re-hashes every grounded entity and names the one that moved — a hash comparison, not a model guess. |
| **Fixing it** | 2:00 | The stale answer is corrected in DataHub. Nothing deleted, everything dated. |
| **The receipts** | 2:05 | The gate reads resolution events straight from SQLite. Every number traces to this run. |
| **End card** | 2:13 | The layer, its five tools, the measured result, where to get it. |

The load-bearing beat is 0:46→0:58: the write-back lands and the next session
inherits it. Everything before is setup; everything after is what happens when the
world moves underneath a stored answer.

## Caption script

Verbatim. `**stars**` render in accent green. Timings are where each caption enters.

| # | Scene | In | Caption |
|---|---|---|---|
| 1 | Hook | 0:00 | Someone / already answered / **this.** / You just / don't know / **it.** |
| 2 | Tagline | 0:05 | **datahub-memory** — a memory layer for DataHub. Five tools, so an answer has somewhere to live. |
| 3 | Autocomplete | 0:08 | Three skills call those tools. This one **investigates.** |
| 4 | Beat A | 0:12 | Memory is empty — so it **goes and earns the answer:** lineage, schemas, documents. |
| 5 | Beat A (1×) | 0:46 | **writeback** puts it in the catalog — watch the description appear. |
| 6 | Inherit | 0:58 | Same question, new session. **memory_recall** answers it — 1 call instead of 16, read from the database. |
| 7 | Drift still | 1:12 | Upstream, **a column was renamed.** |
| 8 | Beat B | 1:15 | Memory that never updates is just **amnesia with better branding.** |
| 9 | Beat B | ~1:40 | **check_freshness** re-hashes every grounded entity and names the one that moved. |
| 10 | Beat B (1×) | 2:00 | The stale answer is **corrected** — nothing deleted, everything dated. |
| 11 | Gate | 2:05 | The gate reads resolution events **straight from SQLite.** Every number in the repo traces to this run. |

## End card

```
datahub-memory                                    (96px, accent)
a memory layer for DataHub                        (34px)
memory_recall · memory_persist · check_freshness
  · writeback_description · writeback_report      (24px)
16× fewer tool calls on repeat questions          (30px, accent)
Claude Code plugin · /datahub-memory:investigate
  · :recall · :writeback                          (26px)
github.com/anthonysuherli/datahub-memory
  · datahub-skills PRs #62 + #69                  (20px)
```

## Honesty constraints held in the captions

- The column rename in beat 3 is applied **before** the recorders start and is shown
  as a still ("Upstream, a column was renamed"). The captions claim only the
  *detection* and the *correction* — both live on camera.
- Caption 5 enters while the pane still reads "No documentation yet"; the fill
  happens ~4s later, inside a 1× real-time bracket. The caption never points at
  something that already happened.
- Caption 6's "1 call instead of 16" is asserted by a counter read from
  `demo/counters-baseline.json`, not from the terminal scrollback.
