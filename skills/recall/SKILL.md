---
name: datahub-memory-recall
description: Memory-first lookup with a deterministic freshness check -- tap the KB via memory_recall, answer straight from the preamble unless the question itself signals the world may have moved on, in which case verify with check_freshness before answering. Use for most DataHub questions; only escalate to /datahub-memory:investigate when coverage is gap.
---

# DataHub Memory — Recall

Answer from what's already known, verified when asked.

## Workflow

1. Call **`memory_recall`** with `project`, `kb`, and the user's question.
   Defaults: `project="dh-demo"`, `kb="main"`.
2. Read the result's `route` field:
   - `route == "investigate"` (coverage `gap`): nothing relevant is banded.
     Hand off to `/datahub-memory:investigate` instead of guessing.
   - `route == "answer_from_memory"` (covers both `rich` and `sparse`
     coverage): continue below.
3. Check whether the **question itself** signals the world may have moved
   on — words like "re-verify", "changed", "drift", "still accurate", "up to
   date".
   - If it does **not**: answer only from the preamble, cite finding ids and
     DataHub URNs, and make no further tool calls.
   - If it **does**: call **`check_freshness`** exactly once, passing the
     entire `grounded` array `memory_recall` returned (not a subset — it
     checks every entity in one deterministic pass). Its `changed` list is a
     hash comparison against DataHub's current state, not a judgment call —
     trust it completely.
     - `changed` empty: answer from the preamble as usual, no further tool
       calls.
     - `changed` non-empty: announce which entities drifted, then hand off
       to `/datahub-memory:investigate` for those specific entities (it will
       `memory_persist` a corrected finding so the resolver can retire the
       stale one) before answering.
4. End the answer with a `Grounded in:` list of URNs.

## Failure modes

- `memory_recall` missing or fails: state that explicitly rather than
  claiming you checked memory.
- Result contains an `error` mentioning a credential: tell the user which
  env var is missing — it must be present in the process environment before
  Claude Code starts (e.g. exported in the shell profile), not just set in
  the plugin root's `.env` (see `.env.example`).
