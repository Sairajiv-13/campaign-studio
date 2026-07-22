"""CLI: ``python -m evals`` — validate the scorer against human A/B preferences."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.config import LlmMode, get_settings
from app.cost import current_total_usd, open_ledger
from app.logging import configure_logging

from evals.guardrails import guardrail_catch_rate
from evals.harness import (
    build_llm,
    default_pairs,
    evaluate,
    format_report,
    to_dict,
)
from evals.metrics import build_report


async def _run(min_accuracy: float, min_guardrail: float, json_path: str | None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    # Meter the run so a real-model eval reports what it actually cost (ADR-004).
    # In sandbox mode this is $0 and the line still prints, which is the point:
    # the number is measured, not asserted.
    with open_ledger():
        results = await evaluate(build_llm(settings), default_pairs())
        run_cost = current_total_usd()
    report = build_report(results)
    catch_rate, catch_n = guardrail_catch_rate()

    model = settings.llm_model if settings.llm_mode is LlmMode.REAL else "sandbox"
    per_pair = run_cost / len(results) if results else 0.0

    print(format_report(report, results))
    print(f"\nguardrail catch rate: {catch_rate:.1%} (n={catch_n})")
    print(f"model:                {model}")
    print(f"run cost:             ${run_cost:.4f} (${per_pair:.4f}/pair, est. at published rates)")
    if json_path:
        payload = {
            **to_dict(report),
            "guardrail_catch_rate": round(catch_rate, 4),
            "model": model,
            "run_cost_usd": round(run_cost, 6),
            "cost_per_pair_usd": round(per_pair, 6),
        }
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\nWrote {json_path}")

    if report.accuracy < min_accuracy:
        print(f"\nFAIL: ranking accuracy {report.accuracy:.1%} below threshold {min_accuracy:.1%}")
        return 1
    if catch_rate < min_guardrail:
        print(f"\nFAIL: guardrail catch rate {catch_rate:.1%} below threshold {min_guardrail:.1%}")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the copy-scorer evaluation.")
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    parser.add_argument("--min-guardrail", type=float, default=1.0)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.min_accuracy, args.min_guardrail, args.json)))


if __name__ == "__main__":
    main()
