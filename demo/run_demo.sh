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

Q="Can I trust monthly_revenue for the board report?"

run_agent() {
  local label="$1" question="$2"
  echo "=== $label ==="
  if ! python -m datahub_memory "$question"; then
    echo "ABORT: $label exited non-zero (see is_error/stop_reason above)" >&2
    exit 1
  fi
}

run_agent "BEAT 1: investigate" "$Q"

run_agent "BEAT 2: inherit" "$Q"

echo "=== BEAT 3: drift ==="
if ! python -m demo.drift; then
  echo "ABORT: drift emission failed" >&2
  exit 1
fi

run_agent "BEAT 3: re-verify" "$Q (re-verify: upstream schema may have changed)"

echo "=== bi-temporal check: findings (live vs retired) ==="
sqlite3 -header -column "$DB_PATH" \
  "select substr(title,1,60) as title,
          case when invalidated_at is not null then 'retired' else 'live' end as status
     from findings order by created_at;"

echo "=== retired_findings count ==="
sqlite3 "$DB_PATH" "select count(*) from findings where invalidated_at is not null;"
