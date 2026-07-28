import asyncio
import json
import sys

from datahub_memory.agent import run_question


def main() -> None:
    question = " ".join(sys.argv[1:]) or "Can I trust monthly_revenue?"
    out = asyncio.run(run_question(question))
    print(out["answer"])
    print(json.dumps(out["counters"]))


if __name__ == "__main__":
    main()
