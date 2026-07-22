"""LLM cost accounting.

A campaign fans out into (segments x channels x variants) generations plus a
brand-voice judge call per variant. Dozens of model calls for one brief. For a
marketing tool that's the whole cost story, and "what did this campaign cost to
generate?" is a question a marketer actually asks. So every LLM call is priced into
a request-scoped ledger and the total is surfaced on the CampaignPlan.

Prices are **published provider rates** (USD per 1M tokens), not a measured bill —
this app has no production deployment and no real spend to report. The sandbox
model is free. Numbers are labeled as estimates wherever they surface (ADR-004).
"""

from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel

# USD per 1M tokens, (input, output). Published list prices as of early 2026;
# update when providers change them. Unknown models fall back to $0 with a note.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "sandbox": (0.0, 0.0),
}


class LlmUsage(BaseModel):
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Cost in USD for one call at published rates. Unknown model -> 0.0."""

    rate_in, rate_out = PRICING.get(model, (0.0, 0.0))
    return (tokens_in * rate_in + tokens_out * rate_out) / 1_000_000


# Request-scoped ledger. Each API request opens one; the LLM adapters append to it
# via record(); the route reads the total. A ContextVar keeps it correctly scoped
# under concurrency without threading a ledger object through every node.
_ledger: ContextVar[list[LlmUsage] | None] = ContextVar("cost_ledger", default=None)


@contextmanager
def open_ledger() -> Iterator[list[LlmUsage]]:
    """Open a fresh ledger for the duration of one request."""

    ledger: list[LlmUsage] = []
    token = _ledger.set(ledger)
    try:
        yield ledger
    finally:
        _ledger.reset(token)


def record(usage: LlmUsage) -> None:
    """Append a usage row to the active ledger, if one is open. A no-op outside a
    request scope (e.g. a bare adapter call in a test) so recording never crashes."""

    ledger = _ledger.get()
    if ledger is not None:
        ledger.append(usage)


def current_total_usd() -> float:
    ledger = _ledger.get()
    return round(sum(row.cost_usd for row in ledger), 6) if ledger else 0.0


class BudgetTracker:
    """Process-local daily spend cap. The last line of defense against a runaway
    bill (ADR-004).

    Honest limitation: this is **in-memory**. Spend resets when the process
    restarts, and across multiple instances each has its own counter. There is no
    shared store here (consistent with the in-memory CampaignStore, ADR-002). It
    stops a runaway loop within one running process; a multi-instance deployment
    would move this to a shared counter. Documented, not hidden.
    """

    def __init__(self, *, warn_usd: float, cap_usd: float) -> None:
        self._warn = warn_usd
        self._cap = cap_usd
        self._lock = threading.Lock()
        self._day = dt.date.today()
        self._spent = 0.0

    def _roll_day(self) -> None:
        today = dt.date.today()
        if today != self._day:
            self._day, self._spent = today, 0.0

    def add(self, usd: float) -> None:
        with self._lock:
            self._roll_day()
            self._spent += usd

    @property
    def spent_today(self) -> float:
        with self._lock:
            self._roll_day()
            return round(self._spent, 6)

    def should_degrade(self) -> bool:
        """True once today's spend has reached the hard cap."""

        return self.spent_today >= self._cap

    def is_warning(self) -> bool:
        return self.spent_today >= self._warn
