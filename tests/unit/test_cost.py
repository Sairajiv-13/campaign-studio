"""Cost accounting + budget breaker unit tests (ADR-004)."""

from __future__ import annotations

from app.cost import (
    BudgetTracker,
    LlmUsage,
    current_total_usd,
    estimate_cost,
    open_ledger,
    record,
)


def test_estimate_cost_uses_published_rates() -> None:
    # gpt-4o: $2.50 in / $10.00 out per 1M tokens.
    assert estimate_cost("gpt-4o", 1_000_000, 0) == 2.50
    assert estimate_cost("gpt-4o", 0, 1_000_000) == 10.00
    assert estimate_cost("gpt-4o", 1000, 1000) == (2.50 + 10.00) / 1000


def test_unknown_model_is_free_not_a_crash() -> None:
    assert estimate_cost("some-future-model", 5000, 5000) == 0.0
    assert estimate_cost("sandbox", 9999, 9999) == 0.0


def test_ledger_accumulates_within_scope_and_resets_after() -> None:
    with open_ledger() as ledger:
        record(LlmUsage(model="gpt-4o", tokens_in=1_000_000, tokens_out=0, cost_usd=2.50))
        record(LlmUsage(model="gpt-4o", tokens_in=0, tokens_out=1_000_000, cost_usd=10.00))
        assert len(ledger) == 2
        assert current_total_usd() == 12.50
    # Outside the scope the ledger is gone and recording is a harmless no-op.
    assert current_total_usd() == 0.0
    record(LlmUsage(model="gpt-4o", tokens_in=1, tokens_out=1, cost_usd=1.0))  # no crash


def test_budget_tracker_trips_at_cap() -> None:
    b = BudgetTracker(warn_usd=1.0, cap_usd=2.0)
    assert not b.should_degrade()
    b.add(1.5)
    assert b.is_warning()
    assert not b.should_degrade()
    b.add(0.6)  # now 2.1 >= cap
    assert b.should_degrade()
    assert b.spent_today == 2.1
