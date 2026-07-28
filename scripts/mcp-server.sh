#!/usr/bin/env bash
# datahub-memory memory MCP server launcher. Portable: uv materializes the
# env from pyproject.toml on first run; no venv paths are baked in anywhere.
set -euo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

if ! command -v uv >/dev/null 2>&1; then
  echo "datahub-memory: 'uv' is required but not installed — get it with:" >&2
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

cd "$ROOT"
exec uv run --project "$ROOT" python -m datahub_memory.mcp_stub
