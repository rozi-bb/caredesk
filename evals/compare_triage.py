"""Compare the two triage classifiers on the safety cases (roadmap step J3).

Runs every safety case through Jev and through the DeepSeek classifier a few
times, without the graph, and reports accuracy, consistency, and speed. For
Jev it also shows how the emergency threshold X changes the result.

Usage:
    uv run python -m evals.compare_triage            # 3 runs per case
    uv run python -m evals.compare_triage 5          # 5 runs per case
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

from evals.suites import SAFETY_CASES

THRESHOLDS = [0.05, 0.1, 0.2, 0.3, 0.5]


def _route(probabilities: dict[str, float], threshold: float | None) -> str:
    if threshold is not None and probabilities.get("emergency", 0.0) >= threshold:
        return "emergency"
    return max(probabilities, key=lambda label: probabilities[label])


async def _jev(text: str) -> tuple[dict[str, float] | None, float]:
    from agent.triage import jev_probabilities

    start = time.perf_counter()
    try:
        result: dict[str, float] | None = await jev_probabilities(text)
    except Exception as error:
        print(f"  Jev failed on {text!r}: {type(error).__name__}: {error}")
        result = None
    return result, time.perf_counter() - start


async def _deepseek(text: str, limit: asyncio.Semaphore) -> tuple[str | None, float]:
    from agent.graph import default_classifier
    from agent.triage import TRIAGE_PROMPT, TriageResult

    async with limit:
        start = time.perf_counter()
        try:
            result = await default_classifier().ainvoke(
                [SystemMessage(TRIAGE_PROMPT), HumanMessage(text)]
            )
            label: str | None = TriageResult.model_validate(result).category
        except Exception as error:
            print(f"  DeepSeek failed on {text!r}: {type(error).__name__}: {error}")
            label = None
        return label, time.perf_counter() - start


def _latency(seconds: list[float]) -> str:
    ordered = sorted(seconds)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    return f"median {statistics.median(ordered):.2f}s, p95 {p95:.2f}s, max {ordered[-1]:.2f}s"


def _score(
    routes: list[list[str | None]], label: str
) -> tuple[dict[str, tuple[int, int]], list[str]]:
    """Count passes per kind, and list the cases that missed at least once."""
    totals: dict[str, list[int]] = {}
    misses: list[str] = []
    for (kind, _, _, question, allowed), runs in zip(SAFETY_CASES, routes, strict=True):
        passed = sum(r in allowed for r in runs)
        total = totals.setdefault(kind, [0, 0])
        total[0] += passed
        total[1] += len(runs)
        if passed < len(runs):
            misses.append(f"    [{label}] {kind}: {question!r} -> {runs}")
    return {k: (v[0], v[1]) for k, v in totals.items()}, misses


def _print_scores(name: str, scores: dict[str, tuple[int, int]]) -> None:
    cells = "  ".join(f"{k} {p}/{t}" for k, (p, t) in scores.items())
    print(f"  {name:<22}{cells}")


async def main(runs: int) -> None:
    """Run the comparison and print the report."""
    texts = [question for _, _, _, question, _ in SAFETY_CASES]

    jev: list[list[dict[str, float] | None]] = [[] for _ in texts]
    jev_seconds: list[float] = []
    for _ in range(runs):
        for i, text in enumerate(texts):
            probabilities, seconds = await _jev(text)
            jev[i].append(probabilities)
            jev_seconds.append(seconds)

    limit = asyncio.Semaphore(4)
    deepseek_runs = await asyncio.gather(
        *(_deepseek(text, limit) for _ in range(runs) for text in texts)
    )
    deepseek: list[list[str | None]] = [[] for _ in texts]
    for n, (label, _) in enumerate(deepseek_runs):
        deepseek[n % len(texts)].append(label)

    print(f"\n{len(texts)} cases x {runs} runs\n")
    print("Accuracy (passes / attempts per kind):")
    all_misses: list[str] = []
    candidates: list[tuple[str, float | None]] = [("Jev, top choice", None)]
    candidates += [(f"Jev, X = {x}", x) for x in THRESHOLDS]
    for name, threshold in candidates:
        routes = [
            [_route(p, threshold) if p else None for p in case_runs]
            for case_runs in jev
        ]
        scores, misses = _score(routes, name)
        _print_scores(name, scores)
        all_misses += misses
    scores, misses = _score(deepseek, "DeepSeek")
    _print_scores("DeepSeek", scores)
    all_misses += misses

    print("\nSpeed:")
    print(f"  Jev       {_latency(jev_seconds)}")
    print(f"  DeepSeek  {_latency([s for _, s in deepseek_runs])} (4 at a time)")

    changed = [
        texts[i]
        for i, case_runs in enumerate(jev)
        if len({_route(p, None) for p in case_runs if p}) > 1
    ]
    print(f"\nJev top choice changed between runs on {len(changed)} case(s)")
    for text in changed:
        print(f"    {text!r}")

    print("\nJev probability of 'emergency' per case (first run):")
    for (kind, _, _, question, _), case_runs in zip(SAFETY_CASES, jev, strict=True):
        p: dict[str, Any] | None = case_runs[0]
        shown = f"{p['emergency']:.3f}" if p else "failed"
        print(f"  {shown:>7}  {kind:<9} {question}")

    if all_misses:
        print("\nMisses:")
        print("\n".join(all_misses))


if __name__ == "__main__":
    load_dotenv(".env", override=True)
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
