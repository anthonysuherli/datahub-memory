# R1 decision: MCP mutation-gating on self-hosted OSS DataHub

**Verified:** 2026-07-27, against a fresh local `docker quickstart`.
**Verdict: mutations, including document ops, are available on OSS DataHub — no
Cloud license required.** Task 5's primary write-back transport is
**`mcp-server-datahub` with `TOOLS_IS_MUTATION_ENABLED=true`**. The Python
emitter/GraphQL fallback described in `docs/design.md` §7 (R1) is not needed for
mutation access itself; keep it only as a non-MCP-runtime fallback (e.g. batch
seeding scripts), not because MCP write access is Cloud-gated.

This directly overturns the design doc's risk framing ("mutation tools need
DataHub Cloud v0.3.17+"). `mcp_server_datahub/version_requirements.py` gates each
mutation tool by version, not by deployment type: `@min_version(cloud="0.3.16",
oss="1.4.0")`. Our quickstart is v1.5.0.6, comfortably above the OSS floor.

## Environment

- DataHub server: **v1.5.0.6** (`acryldata/datahub`), quickstart plan pulled by
  `datahub` CLI **1.6.0.16**. Confirmed via `curl localhost:8080/config` →
  `"versions": {"acryldata/datahub": {"version": "v1.5.0.6", ...}}` and via the
  MCP server's own version probe log line: `Server version info for
  http://localhost:8080: is_cloud=False, version=(1, 5, 0, 6)`.
- `mcp-server-datahub`: **v0.6.0** (`uvx mcp-server-datahub --version`). Meets the
  plan's "v0.5.0+" floor.
- GMS at `http://localhost:8080`, frontend at `http://localhost:9002`.
- Auth: `METADATA_SERVICE_AUTH` is effectively **enabled** on this quickstart —
  unauthenticated GraphQL calls are rejected and a real bearer token is required
  for the REST/GraphQL APIs the MCP server calls. Token generation worked (see
  below); the brief's "auth disabled" contingency did not apply here.

## What we ran

```bash
.venv/bin/pip install 'acryl-datahub[datahub-rest]'
DATAHUB_TELEMETRY_ENABLED=false .venv/bin/datahub docker quickstart
.venv/bin/datahub docker check   # -> "No issues detected"
```

**Gotcha (recorded in `demo/quickstart.sh`):** the CLI's Mixpanel telemetry ping
to `track.datahubproject.io` hangs indefinitely (TCP `SYN_SENT`, no RST, no
timeout enforced) on this sandbox's network — it silently wedges `datahub
docker quickstart` and `mcp-server-datahub` before either does anything useful.
Fix: `DATAHUB_TELEMETRY_ENABLED=false` in the environment for both the CLI and
the MCP server process. Without it, expect an indefinite hang, not a timeout.

Login + token, scripted (no browser), matching the brief's suggested path:

```bash
curl -c cookies.txt -H 'Content-Type: application/json' \
  -d '{"username":"datahub","password":"datahub"}' http://localhost:9002/logIn
curl -b cookies.txt -H 'Content-Type: application/json' \
  -d '{"query":"mutation createAccessToken($input: CreateAccessTokenInput!) { createAccessToken(input: $input) { accessToken } }",
       "variables":{"input":{"type":"PERSONAL","actorUrn":"urn:li:corpuser:datahub","duration":"ONE_MONTH","name":"datahub-memory"}}}' \
  http://localhost:9002/api/v2/graphql
```

**Gotcha:** the first attempt(s) right after `docker check` reports healthy
return `403 Unauthorized to perform this action` for `createAccessToken`, even
for the root `datahub` user. Cause, confirmed from GMS logs: the bootstrap
`IngestPoliciesStep` *does* ingest an `admin-platform-policy` granting
`GENERATE_PERSONAL_ACCESS_TOKENS`, but the policy index isn't queryable by the
authorizer for roughly 30-60s after GMS reports healthy. Querying `me {
platformPrivileges { generatePersonalAccessTokens } }` returned `false` for the
first 5 polls (10s apart) and flipped to `true` on the 6th. `demo/quickstart.sh`
now retries the token mutation for up to 2 minutes instead of failing on first
403. This is a propagation-lag issue, not a real capability gap — record it so
Task 5/6 don't misread a transient 403 as "tokens are disabled."

Token verified against GMS directly: `curl -H "Authorization: Bearer $TOKEN"
localhost:8080/config` → 200 with the same config payload.

## MCP tool inventory (both ways)

Listed with `demo/list_mcp_tools.py` (stdio JSON-RPC: initialize →
notifications/initialized → tools/list), against the live quickstart above.
Ran with `DATAHUB_GMS_URL`/`DATAHUB_GMS_TOKEN` from `.env.local` and
`DATAHUB_TELEMETRY_ENABLED=false` (the server has its own, separate telemetry
ping to the same host, gated by the same CLI env var — same hang, same fix).

Document-search tools (`search_documents`, `grep_documents`) are gated by
**catalog content**, not by `TOOLS_IS_MUTATION_ENABLED` — the server probes
`documentSearch` on every `tools/list` call and hides those two tools while the
Document catalog is empty. Counts below are shown both ways.

### Default env (`TOOLS_IS_MUTATION_ENABLED` unset) — read-only

Empty document catalog — **6 tools**:
```
search, get_lineage, get_dataset_queries, get_entities, list_schema_fields,
get_lineage_paths_between
```

After a document exists (see below) — **8 tools** (adds `search_documents`,
`grep_documents`):
```
search, get_lineage, get_dataset_queries, get_entities, list_schema_fields,
get_lineage_paths_between, search_documents, grep_documents
```

No mutation tools appear either way. Log line confirms the gate:
`register_mutation_tools:230 - Mutation Tools DISABLED MCP Server.`

### `TOOLS_IS_MUTATION_ENABLED=true` — mutations exposed

Empty document catalog — **18 tools** (adds the 12 below to the read set):
```
search, get_lineage, get_dataset_queries, get_entities, list_schema_fields,
get_lineage_paths_between, add_tags, remove_tags, add_terms, remove_terms,
add_owners, remove_owners, set_domains, remove_domains, update_description,
add_structured_properties, remove_structured_properties, save_document
```

After a document exists — **20 tools** (full set, adds `search_documents`,
`grep_documents`):
```
search, get_lineage, get_dataset_queries, get_entities, list_schema_fields,
get_lineage_paths_between, search_documents, grep_documents, add_tags,
remove_tags, add_terms, remove_terms, add_owners, remove_owners, set_domains,
remove_domains, update_description, add_structured_properties,
remove_structured_properties, save_document
```

Log lines confirm: `register_mutation_tools:230 - Mutation Tools ENABLED MCP
Server.` / `register_mutation_tools:268 - Save Document ENABLED - registering
save_document tool`.

`TOOLS_IS_USER_ENABLED` and data-quality tools (`get_dataset_assertions`, cloud
only per `@min_version(cloud="0.3.16")` with no `oss=` — i.e. genuinely
unavailable on OSS regardless of flags) were left at their defaults
(disabled/unavailable); not part of R1's scope but noted for completeness.

**Drift from `docs/design.md`:** the design doc's architecture diagram states
"22 tools: 10 read / 12 write". Empirically, with mutations on and a non-empty
catalog, the real count is 20 (8 read + 12 write). Not a blocker, just flag it
— update the diagram's tool count in a later task if it matters for the demo
narrative.

## Document ops — functional proof, not just registration (needs OSS ≥ 1.4.x)

`save_document` carries `@min_version(cloud="0.3.16", oss="1.4.0")` in
`mcp_server_datahub/version_requirements.py` — confirmed by reading the source
(`tools/save_document.py`, `tools/terms.py`, `tools/tags.py`,
`tools/structured_properties.py`, `tools/owners.py`, `tools/domains.py`,
`tools/descriptions.py` all carry the identical `oss="1.4.0"` floor). Our
quickstart (v1.5.0.6) clears it, so every one of the 12 mutation tools is
present in the listing above — none were silently filtered by the
version-gating middleware.

Beyond just listing the tool, we called it end-to-end:

```python
await session.call_tool("save_document", {
    "title": "R1 verification doc",
    "content": "Created by datahub-memory Task 2 R1 verification script.",
    "document_type": "Note",   # enum: Insight|Decision|FAQ|Analysis|Summary|Recommendation|Note|Context
})
```

Result: `isError: False`, GMS logs show
`Successfully created document: urn:li:document:shared-91084f36-025b-4678-b403-1e5025f8b25a`
under the `__system_shared_documents` parent folder. This is real evidence the
write path works against this OSS build, not just that the tool registers.

## Decision for Task 5

- **Primary write-back transport: `mcp-server-datahub` over stdio, with
  `TOOLS_IS_MUTATION_ENABLED=true` in its process env.** No Cloud trial, no
  emitter fallback needed for the demo. `save_document`, `update_description`,
  `add_terms`/`add_tags` (for glossary-term proposals per the design doc's
  human-in-the-loop beat), and `add_structured_properties` are all live.
- Keep `writeback/`'s Python-emitter/GraphQL path in the codebase only as a
  defensive fallback (e.g. if a judge's environment somehow can't run `uvx`, or
  for bulk/non-interactive seeding in `demo/`) — not because MCP mutations are
  gated. Update the README's Cloud-only caveat: it should say "MCP mutation
  tools are OSS-available given `TOOLS_IS_MUTATION_ENABLED=true` and DataHub
  ≥1.4.x; no Cloud license required," not "Cloud-only."
- Two operational gotchas to carry into Task 5/6 env setup:
  1. Set `DATAHUB_TELEMETRY_ENABLED=false` for both the `datahub` CLI and any
     process that imports `mcp_server_datahub` — otherwise a blocked telemetry
     host causes an indefinite hang, not a clean timeout.
  2. Personal-access-token creation (and any privilege check on the root user)
     can 403 for ~30-60s immediately after `docker check` reports healthy.
     Retry, don't treat the first 403 as "auth is disabled."

## Files

- `demo/quickstart.sh` — scripted bring-up: telemetry-safe `docker quickstart`,
  health check, version check, login, token creation (with retry), writes
  `.env.local`.
- `demo/list_mcp_tools.py` — stdio MCP client (`initialize` →
  `notifications/initialized` → `tools/list`) used for both listings above;
  reusable by Task 6 for any further tool-surface checks.
- `.env.local` (git-ignored) — `DATAHUB_GMS_URL=http://localhost:8080`,
  `DATAHUB_GMS_TOKEN=<personal access token>`.
