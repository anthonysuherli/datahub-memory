import asyncio
import json
import os
import sys
from pathlib import Path

# Reproducibility (review finding Important-1): delapan defaults to
# ~/.delapan/delapan.db when DELAPAN_DB_PATH is unset (delapan/store/sqlite.py
# _default_db_path), so on a fresh clone the demo memory would silently land
# outside this repo's ".data/" constraint. Pin it before importing/running the
# agent (which pulls in delapan transitively via bridge.py) so every run uses
# a repo-local DB unless the caller has already set their own.
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / ".data" / "delapan.db"
os.environ.setdefault("DELAPAN_DB_PATH", str(_DEFAULT_DB_PATH))
Path(os.environ["DELAPAN_DB_PATH"]).parent.mkdir(parents=True, exist_ok=True)

from datahub_memory.agent import run_question


def main() -> None:
    question = " ".join(sys.argv[1:]) or "Can I trust monthly_revenue?"
    out = asyncio.run(run_question(question))
    print(out["answer"])
    print(json.dumps(out["counters"]))
    if out.get("is_error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
