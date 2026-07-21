# Security

The threat model this studio is built against, the controls in place, and what it
does *not* defend against. The gaps are listed on purpose (ADR-009) — a security doc
that only lists strengths is marketing.

## What we're protecting

A service that takes an untrusted **brief**, feeds it to an LLM, and returns
generated marketing copy that a human will review and eventually send to real
customers. Money is attached (LLM spend). The system takes **no external actions** —
it opens no tickets, sends no mail, calls no tools — which deliberately keeps the
blast radius of a bad generation at "bad copy", not "bad copy that got sent".

## Controls in place

| Risk | Control | Where |
|------|---------|-------|
| Unauthorized use | JWT bearer auth with scopes (`campaigns:write`, `campaigns:read`) | `security/jwt.py`, `auth.py` |
| Insecure production boot | Refuses to start in production with the default or a <32-char `JWT_SECRET` | `config.py` |
| Abuse / floods | Rate limiting + body-size cap (413) | `security/rate_limit.py`, `observability.py` |
| **Prompt injection** | User values are whitespace-flattened so they can't forge a `label: value` line or append instructions | `prompting.py`, ADR-010 |
| **Stored XSS in the demo UI** | Model-produced `notes` escaped before `innerHTML`; `escape()` covers quotes for attribute safety | `web/index.html`, ADR-010 |
| Malformed input | Control-character stripping, length caps, segment/variant caps at the boundary | `api/schemas.py` |
| Runaway LLM cost | Per-campaign cost accounting + daily budget breaker that degrades to sandbox | `cost.py`, ADR-004 |
| Paying twice for the same work | Brief fingerprinting (model label included) | `idempotency.py`, ADR-006 |
| Brand/compliance damage | Deterministic guardrail; hard flags can't win a segment | `guardrails.py`, ADR-007 |

## Known limitations (what this does NOT do)

- **Injection is contained, not solved.** Flattening removes the ability to forge a
  prompt *line*; it can't stop a model from being influenced by hostile text inside a
  legitimate field. The real containment is that model output here is content, not
  actions (ADR-010).
- **JWT is symmetric (HS256), with no rotation or revocation.** Tokens are bearer —
  whoever holds one is the principal. A multi-service deployment wants RS256/JWKS.
- **Rate limiting is per-process.** Behind more than one instance the limit is
  per-instance, not global.
- **State is in-memory** (ADR-002). There's no data at rest to protect, but equally
  no audit trail — campaigns, cache, and the spend counter vanish on restart.
- **Spend is a local estimate**, not a reconciled bill; it's a guardrail signal, and
  it resets on restart, so it can't be relied on as a hard spend ceiling across
  restarts.
- **No secrets manager, no dependency-scanning gate.** Secrets come from the
  environment; deps are pinned. Adding `pip-audit`/Dependabot to CI is a clear next
  step.
- **The demo UI is a demo.** It's a single unbuilt HTML file for exercising the API,
  not a hardened front end — no CSP, no framework escaping guarantees beyond the
  explicit `escape()` calls.

## Reporting

This is a portfolio project, not a hosted service. If you're reviewing it and find
something — especially a gap not listed above — please open an issue.
