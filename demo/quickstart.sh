#!/usr/bin/env bash
# Bring up a local DataHub instance and verify it, then generate a personal
# access token and write DATAHUB_GMS_URL / DATAHUB_GMS_TOKEN to .env.local.
#
# Prerequisites: Docker daemon running, .venv set up (see repo README).
#
# Run from the repo root: demo/quickstart.sh
set -euo pipefail

cd "$(dirname "$0")/.."

VENV_BIN=".venv/bin"

# The CLI's Mixpanel telemetry ping (track.datahubproject.io/mp) hangs
# indefinitely (SYN_SENT, no RST) on networks that block that AWS endpoint --
# observed in this sandbox. Disable it so `docker quickstart` doesn't wedge
# before it even starts pulling images.
export DATAHUB_TELEMETRY_ENABLED=false

echo "== Installing acryl-datahub[datahub-rest] =="
"$VENV_BIN/pip" install 'acryl-datahub[datahub-rest]'

echo "== Bringing up DataHub via docker quickstart (5-15 min on first pull) =="
"$VENV_BIN/datahub" docker quickstart

echo "== Checking container health =="
"$VENV_BIN/datahub" docker check

echo "== Recording server version (must be >= 1.4.x for document ops) =="
curl -s localhost:8080/config | python3 -m json.tool | grep -i version

echo "== Logging in to the frontend to get a session cookie =="
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT
curl -s -c "$COOKIE_JAR" -H 'Content-Type: application/json' \
  -d '{"username":"datahub","password":"datahub"}' \
  http://localhost:9002/logIn

echo "== Creating a personal access token via GraphQL =="
# The root "datahub" user's platform privileges (incl. generatePersonalAccessTokens)
# come from a policy index that isn't queryable immediately after GMS reports
# healthy -- the first attempt(s) right after a fresh quickstart reliably 403
# with "Unauthorized to perform this action" for ~30-60s. Retry instead of
# failing hard.
TOKEN_MUTATION='{"query":"mutation createAccessToken($input: CreateAccessTokenInput!) { createAccessToken(input: $input) { accessToken } }","variables":{"input":{"type":"PERSONAL","actorUrn":"urn:li:corpuser:datahub","duration":"ONE_MONTH","name":"datahub-memory"}}}'
TOKEN_RESPONSE=""
for attempt in $(seq 1 12); do
  TOKEN_RESPONSE="$(curl -s -b "$COOKIE_JAR" -H 'Content-Type: application/json' \
    -d "$TOKEN_MUTATION" http://localhost:9002/api/v2/graphql)"
  if echo "$TOKEN_RESPONSE" | grep -q '"accessToken"'; then
    break
  fi
  echo "  attempt $attempt: not authorized yet, retrying in 10s..."
  sleep 10
done
echo "$TOKEN_RESPONSE"

TOKEN="$(echo "$TOKEN_RESPONSE" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data",{}).get("createAccessToken",{}).get("accessToken",""))')"

if [ -n "$TOKEN" ]; then
  cat > .env.local <<EOF
export DATAHUB_GMS_URL=http://localhost:8080
export DATAHUB_GMS_TOKEN=$TOKEN
export DLP_MEMORY__ENABLED=true
export DELAPAN_DB_PATH="$PWD/.data/delapan.db"
EOF
  echo "== Wrote .env.local =="
else
  echo "== Token creation returned no token after $attempt attempts (see response above) =="
  echo "== Either METADATA_SERVICE_AUTH is disabled on this GMS, or the root user's platform"
  echo "== policy still hasn't propagated -- try re-running this script, or generate a token"
  echo "== manually via http://localhost:9002/settings/tokens. Recording GMS URL only. =="
  cat > .env.local <<EOF
export DATAHUB_GMS_URL=http://localhost:8080
export DATAHUB_GMS_TOKEN=
export DLP_MEMORY__ENABLED=true
export DELAPAN_DB_PATH="$PWD/.data/delapan.db"
EOF
fi

echo "== Done. Source .env.local in your shell before running other demo/ scripts. =="
