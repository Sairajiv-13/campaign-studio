"""Metrics for the scorer evaluation.

The headline is pairwise ranking accuracy: on each labeled A/B pair, does the
scorer give the human-preferred variant the higher composite? We also break
accuracy down by the lever each pair isolates, and report the mean score margin
(how decisively the scorer separates the pair).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PairResult:
    id: str
    dimension: str
    predicted: str
    preferred: str
    composite_preferred: float
    composite_other: float

    @property
    def correct(self) -> bool:
        return self.predicted == self.preferred

    @property
    def margin(self) -> float:
        return abs(self.composite_preferred - self.composite_other)


@dataclass(frozen=True)
class EvalReport:
    n: int
    accuracy: float
    mean_margin: float
    by_dimension: dict[str, float]


def build_report(results: list[PairResult]) -> EvalReport:
    if not results:
        raise ValueError("no results to report")

    n = len(results)
    accuracy = sum(1 for r in results if r.correct) / n
    mean_margin = sum(r.margin for r in results) / n

    by_dimension: dict[str, float] = {}
    dims = sorted({r.dimension for r in results})
    for dim in dims:
        subset = [r for r in results if r.dimension == dim]
        by_dimension[dim] = sum(1 for r in subset if r.correct) / len(subset)

    return EvalReport(n=n, accuracy=accuracy, mean_margin=mean_margin, by_dimension=by_dimension)
