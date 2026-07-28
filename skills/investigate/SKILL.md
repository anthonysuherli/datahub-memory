---
name: datahub-memory-investigate
description: Run the full memory-first DataHub investigation loop -- recall prior grounded findings, walk lineage and institutional memory when memory is thin or gap, persist new findings, and write back a description/report. Use when the user asks a trust/investigation question about a DataHub dataset ("can I trust X", "what happened to Y", "investigate Z") that recall alone can't answer.
---

# DataHub Memory — Investigate

Full agent loop: memory-first, DataHub-grounded, write back what you learn.

## Workflow

1. Call **`memory_recall`** with `project`, `kb`, and the user's question first —
   always, before touching DataHub. Defaults: `project="dh-demo"`, `kb="main"`
   (the demo catalog) unless the user names another.
2. Branch on the result's `route` field (not the raw `coverage` string):
   - `route == "answer_from_memory"` (covers both `rich` and `sparse`
     coverage): hand off to `/datahub-memory:recall` — its staleness/
     freshness-check logic applies, not a fresh investigation.
   - `route == "investigate"` (coverage `gap` — nothing relevant banded at
     all): continue below.
3. **Investigate with the DataHub tools**: `search` -> `get_entities` ->
   `get_lineage` (walk upstream) -> read descriptions/institutional memory on
   **every** entity in the lineage chain, not just the one asked about —
   incidents are frequently recorded on the upstream root source, not the
   dataset the user named. Use `get_dataset_queries` when SQL context helps.
   Surface any incident you find even if it reads as already resolved; never
   report "no incidents" without having checked institutional memory on every
   upstream entity.
4. **Conclude and persist**: call **`memory_persist`** ONCE PER DISTINCT
   CONCLUSION (aim for 2-4 calls per investigation — e.g. the overall trust
   verdict, an incident's impact on the numbers, the lineage structure
   walked, a data-quality observation). Skip a category only if you
   genuinely found nothing to say. Each call's `grounded` list needs one
   entry per DataHub URN that conclusion relies on, and **every** entry must
   carry that entity's `schema_fields` (from `get_entities`/
   `list_schema_fields`) and `upstream_urns` (from `get_lineage`) — omitting
   them collapses every entity to the same placeholder grounding hash and
   silently breaks drift detection. Carry `ui_url` when available.
5. **Write back** — hand off to `/datahub-memory:writeback` for the
   description fill / report attach.
6. End the answer with a `Grounded in:` list of URNs. Be concise; state an
   explicit verdict (trusted / trusted-with-caveat / not trusted).

## Failure modes

- No available tool exposes institutional memory (`memory_recall` missing or
  fails): say so explicitly rather than claiming you checked.
- `DATAHUB_GMS_URL` unset for the `datahub` MCP server: DataHub tool calls
  will fail outright — tell the user to set it (see plugin `.env.example`).
