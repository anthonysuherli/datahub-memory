#!/usr/bin/env bash
# Scripted 3-beat demo: investigate -> inherit from memory -> drift + re-verify.
# Run from repo root: demo/run_demo.sh (after sourcing .env.local).
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source .venv/bin/activate

# The CLI/MCP server's Mixpanel telemetry ping hangs indefinitely on networks
# that block it (see docs/R1-decision.md) -- disable it for this whole run,
# not just for the parent process, since mcp-server-datahub is spawned fresh
# per agent turn and would otherwise inherit an unset value.
export DATAHUB_TELEMETRY_ENABLED=false

DB_PATH="${DELAPAN_DB_PATH:-$PWD/.data/delapan.db}"

echo "== Fresh state: removing $DB_PATH so beat 1 starts from gap =="
rm -f "$DB_PATH"

# Discovered live (2026-07-28): removing delapan's local memory alone is NOT
# a fresh state. Beat 1's/beat 3's own write-back (update_description,
# save_document) mutates DataHub itself, and that leaks forward -- a prior
# run's agent can write "field renamed to amount" straight into
# stg_payments' EditableDatasetProperties or into a freshly-titled document,
# which a SUBSEQUENT "fresh" run's beat 1 then reads back as prior knowledge
# before demo/drift.py has even run in that sequence. Reset both: clear
# EditableDatasetProperties on the seeded datasets, and delete every
# save_document-created document except the one seed.py itself maintains.
echo "== Fresh state: resetting DataHub write-back residue from prior runs =="
python - <<'PY'
import asyncio
import json
import os

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.ingestion.graph.client import DataHubGraph
from datahub.ingestion.graph.config import DatahubClientConfig
from datahub.metadata.schema_classes import EditableDatasetPropertiesClass
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from demo.seed import INCIDENT_TITLE, URNS


def reset_editable_properties() -> None:
    emitter = DatahubRestEmitter(gms_server=os.environ["DATAHUB_GMS_URL"],
                                  token=os.environ.get("DATAHUB_GMS_TOKEN"))
    for urn in URNS.values():
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=urn, aspect=EditableDatasetPropertiesClass(description="")))


def _tool_text(result) -> str:
    for block in getattr(result, "content", None) or []:
        if hasattr(block, "text"):
            return block.text
    return ""


async def delete_stray_documents() -> None:
    env = dict(os.environ)
    env["TOOLS_IS_MUTATION_ENABLED"] = "true"
    env["DATAHUB_TELEMETRY_ENABLED"] = "false"
    params = StdioServerParameters(command="uvx", args=["mcp-server-datahub"], env=env)
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        try:
            res = await s.call_tool("search_documents", {"query": "*", "num_results": 50})
            data = json.loads(_tool_text(res) or "{}")
        except Exception as exc:  # noqa: BLE001 -- degrade: nothing to clean up
            print(f"  (search_documents unavailable: {exc}; skipping document cleanup)")
            return

        stray = []
        for row in data.get("searchResults", []):
            entity = row.get("entity", {})
            urn = entity.get("urn", "")
            title = (entity.get("info") or {}).get("title")
            if urn.endswith(":__system_shared_documents") or title == INCIDENT_TITLE:
                continue
            stray.append(urn)

        if not stray:
            return
        print(f"  deleting {len(stray)} stray document(s) left by prior runs")
        graph = DataHubGraph(DatahubClientConfig(
            server=os.environ["DATAHUB_GMS_URL"], token=os.environ.get("DATAHUB_GMS_TOKEN")))
        for urn in stray:
            graph.hard_delete_entity(urn)


reset_editable_properties()
asyncio.run(delete_stray_documents())
print("  DataHub write-back residue reset")
PY

# Re-affirm the seeded schema/lineage/incident doc baseline (idempotent, no
# live-agent spend) in case a prior run's demo/drift.py left stg_payments
# renamed without a following demo/seed.py re-run.
echo "== Fresh state: re-affirming seed baseline (schema, lineage, incident doc) =="
python -m demo.seed

Q="Can I trust monthly_revenue for the board report?"

run_agent() {
  local label="$1" question="$2"
  echo "=== $label ==="
  if ! python -m datahub_memory "$question"; then
    echo "ABORT: $label exited non-zero (see is_error/stop_reason above)" >&2
    exit 1
  fi
}

# resolution_events op counts as "op:count" lines -- the ground truth for which
# resolver op fired, since findings.invalidated_at alone can't distinguish
# UPDATE from SUPERSEDE (both retire the row) and can't be pinned to a beat.
snapshot_ops() {
  [ -f "$DB_PATH" ] || return 0
  sqlite3 "$DB_PATH" \
    "select op || ':' || count(*) from resolution_events group by op order by op;" \
    2>/dev/null || true
}

# ops_delta BEFORE AFTER: per-op count increase between two snapshots.
ops_delta() {
  python - "$1" "$2" <<'PY'
import sys

def parse(s):
    d = {}
    for line in s.splitlines():
        if not line.strip():
            continue
        op, n = line.rsplit(":", 1)
        d[op] = int(n)
    return d

before, after = parse(sys.argv[1]), parse(sys.argv[2])
ops = sorted(set(before) | set(after))
fired = False
for op in ops:
    delta = after.get(op, 0) - before.get(op, 0)
    if delta:
        print(f"  {op}: +{delta}")
        fired = True
if not fired:
    print("  (no new resolution_events)")
PY
}

BEFORE_1="$(snapshot_ops)"
run_agent "BEAT 1: investigate" "$Q"
AFTER_1="$(snapshot_ops)"
echo "--- resolution_events delta after beat 1 ---"
ops_delta "$BEFORE_1" "$AFTER_1"

run_agent "BEAT 2: inherit" "$Q"
AFTER_2="$(snapshot_ops)"
echo "--- resolution_events delta after beat 2 ---"
ops_delta "$AFTER_1" "$AFTER_2"

echo "=== BEAT 3: drift ==="
if ! python -m demo.drift; then
  echo "ABORT: drift emission failed" >&2
  exit 1
fi
BEFORE_3="$(snapshot_ops)"  # drift.py doesn't touch delapan's db; equals AFTER_2

run_agent "BEAT 3: re-verify" "$Q (re-verify: upstream schema may have changed)"
AFTER_3="$(snapshot_ops)"
echo "--- resolution_events delta after beat 3 (re-verify) ---"
DELTA_3="$(ops_delta "$BEFORE_3" "$AFTER_3")"
echo "$DELTA_3"

if ! echo "$DELTA_3" | grep -q "SUPERSEDE:"; then
  echo "ABORT: beat 3 did not produce a SUPERSEDE resolution op." >&2
  echo "       ops that DID fire this beat:" >&2
  echo "$DELTA_3" >&2
  exit 1
fi

echo "=== bi-temporal check: findings (live vs retired) ==="
sqlite3 -header -column "$DB_PATH" \
  "select substr(title,1,60) as title,
          case when invalidated_at is not null then 'retired' else 'live' end as status
     from findings order by created_at;"

echo "=== retired_findings count ==="
sqlite3 "$DB_PATH" "select count(*) from findings where invalidated_at is not null;"
