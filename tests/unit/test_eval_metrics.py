"""Unit tests for the eval metric aggregation."""

from __future__ import annotations

import pytest
from evals.metrics import PairResult, build_report


def _r(id_: str, dim: str, predicted: str, preferred: str, a: float, b: float) -> PairResult:
    return PairResult(
        id=id_,
        dimension=dim,
        predicted=predicted,
        preferred=preferred,
        composite_preferred=a,
        composite_other=b,
    )


def test_build_report_accuracy_and_margin() -> None:
    results = [
        _r("p1", "cta", "a", "a", 0.8, 0.6),  # correct, margin 0.2
        _r("p2", "cta", "a", "b", 0.5, 0.7),  # wrong, margin 0.2
        _r("p3", "spam", "b", "b", 0.9, 0.3),  # correct, margin 0.6
    ]
    report = build_report(results)
    assert report.n == 3
    assert report.accuracy == pytest.approx(2 / 3)
    assert report.mean_margin == pytest.approx((0.2 + 0.2 + 0.6) / 3)
    assert report.by_dimension["cta"] == pytest.approx(0.5)
    assert report.by_dimension["spam"] == pytest.approx(1.0)


def test_build_report_rejects_empty() -> None:
    with pytest.raises(ValueError):
        build_report([])
