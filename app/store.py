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

    def save(self, plan: CampaignPlan) -> None:
        with self._lock:
            self._plans[plan.id] = plan

    def get(self, campaign_id: str) -> CampaignPlan | None:
        with self._lock:
            return self._plans.get(campaign_id)

    def count(self) -> int:
        with self._lock:
            return len(self._plans)
