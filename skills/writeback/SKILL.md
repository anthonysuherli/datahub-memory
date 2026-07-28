---
name: datahub-memory-writeback
description: Attach a description or investigation report to a DataHub entity -- mutation tools (update_description, save_document) are the primary path, the writeback_description/writeback_report emitter fallback tools are used ONLY if a mutation tool call fails. Use after an investigation reaches a conclusion worth recording on the entity itself.
---

# DataHub Memory — Write Back

Record what was learned on the entity itself, not just in the KB.

## Workflow

1. **Primary path — DataHub's own MCP mutation tools** (require
   `TOOLS_IS_MUTATION_ENABLED=true`, already set in this plugin's `mcp.json`):
   - `update_description` to fill an empty/stale dataset description you can
     now write authoritatively.
   - `save_document` to attach the investigation report.
   - (`add_terms` / `add_tags` are also available on the `datahub` MCP server
     for glossary-term proposals, if relevant.)
2. **Fallback — only if a mutation tool call fails**: use the `memory`
   server's own emitter-backed tools instead:
   - **`writeback_description`** with `urn`, `description`.
   - **`writeback_report`** with `urn`, `title`, `markdown`.

   Both do read-modify-write against the entity's current aspect (never a
   wholesale replace) and degrade instead of raising: a failure comes back as
   `{"ok": false, "transport": "emitter", "detail": ...}` rather than a
   crash — relay `detail` to the user, don't retry silently.
3. Do not call the fallback tools speculatively "just in case" — only after
   the corresponding mutation tool call has actually failed.

## Failure modes

- `ok: false` from `writeback_description`/`writeback_report`: relay the
  `detail` field verbatim (e.g. GMS unreachable) — do not report the write
  as successful.
- `DATAHUB_GMS_URL` unset: both the mutation tools and the fallback tools
  will fail — tell the user to set it (see plugin `.env.example`).
