"""Brief fingerprinting for idempotent generation.

Generating a campaign costs real model calls (ADR-004). Submitting the *same brief*
twice — a double-click, a retry, a marketer re-running an unchanged brief — should
not pay to regenerate it. So each brief gets a deterministic fingerprint; if a plan
for that fingerprint already exists, we return it instead of regenerating
(ADR-006). `force=true` opts out when the marketer wants fresh variants.

The fingerprint includes the model label: a plan generated on the sandbox must not
be served back when the deployment has since switched to a real model, because the
copy would be different.
"""

from __future__ import annotations

import hashlib

from app.domain.models import Brief


def brief_fingerprint(brief: Brief, *, model_label: str) -> str:
    """A stable hash of the brief's content + the model that would generate it.

    Uses Pydantic's canonical JSON (sorted, mode="json") so semantically identical
    briefs hash identically regardless of field insertion order.
    """

    canonical = brief.model_dump_json()
    payload = f"{model_label}\n{canonical}".encode()
    return hashlib.sha256(payload).hexdigest()
