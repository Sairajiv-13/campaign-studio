"""In-memory campaign store.

Persistence is not this project's story — generation and scoring are — so campaigns
live in process memory behind a small interface. The interface is the seam: swap in
Postgres/Redis without touching the API or pipeline.
"""

from __future__ import annotations

import threading

from app.domain.models import CampaignPlan


class CampaignStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plans: dict[str, CampaignPlan] = {}
        # Brief fingerprint -> campaign id, for the "don't regenerate the same
        # brief" idempotency path (ADR-006).
        self._by_fingerprint: dict[str, str] = {}

    def save(self, plan: CampaignPlan, *, fingerprint: str | None = None) -> None:
        with self._lock:
            self._plans[plan.id] = plan
            if fingerprint is not None:
                self._by_fingerprint[fingerprint] = plan.id

    def get(self, campaign_id: str) -> CampaignPlan | None:
        with self._lock:
            return self._plans.get(campaign_id)

    def get_by_fingerprint(self, fingerprint: str) -> CampaignPlan | None:
        with self._lock:
            campaign_id = self._by_fingerprint.get(fingerprint)
            return self._plans.get(campaign_id) if campaign_id else None

    def count(self) -> int:
        with self._lock:
            return len(self._plans)
