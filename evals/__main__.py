"""CLI: ``python -m evals`` — validate the scorer against human A/B preferences."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.config import get_settings
from app.logging import configure_logging

from evals.harness import (
    build_llm,
    default_pairs,
    evaluate,
    format_report,
    to_dict,
)
from evals.metrics import build_report


async def _run(min_accuracy: float, json_path: str | None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    results = await evaluate(build_llm(settings), default_pairs())
    report = build_report(results)

    print(format_report(report, results))
    if json_path:
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(to_dict(report), handle, indent=2)
        print(f"\nWrote {json_path}")

    if report.accuracy < min_accuracy:
        print(f"\nFAIL: ranking accuracy {report.accuracy:.1%} below threshold {min_accuracy:.1%}")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the copy-scorer evaluation.")
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.min_accuracy, args.json)))


if __name__ == "__main__":
    main()
