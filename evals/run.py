"""Run evaluation suites against LangSmith.

Usage:
    uv run python -m evals.run                      # every suite
    uv run python -m evals.run access_control       # one or more by name
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv
from langsmith import Client

from evals.harness import fresh_database, run_suite
from evals.suites import SUITES


async def main(names: list[str]) -> int:
    """Run the named suites and return a non-zero exit code when a suite misses a target."""
    unknown = [n for n in names if n not in SUITES]
    if unknown:
        print(
            f"Unknown suite(s): {', '.join(unknown)}. Choose from: {', '.join(SUITES)}"
        )
        return 2
    db = fresh_database()
    client = Client()
    ok = True
    for name in names or list(SUITES):
        ok = await run_suite(client, SUITES[name], db) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    load_dotenv(".env", override=True)
    sys.exit(asyncio.run(main(sys.argv[1:])))
