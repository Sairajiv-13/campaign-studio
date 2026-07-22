# Troubleshooting

Real problems you can hit running this repo, and the fix. If something here is
wrong, it's a bug in the docs. Fix it.

## Setup

### `pip install` fails building a wheel
This project targets **Python 3.12** (CI and the Docker image both use it). Newer
interpreters don't yet have wheels for some pinned deps:

```bash
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
```

### The studio starts but generation is slow / hangs on a real model
`LLM_MODE=real` points at an OpenAI-compatible endpoint (Ollama by default). Local
inference needs real RAM. On a small machine a 3B model swaps to disk and takes
minutes per call, and this pipeline makes **one call per segment × channel** plus a
judge call per variant, so a 3-segment brief is a dozen-plus calls. This is a
hardware limit, not a bug. The default `LLM_MODE=sandbox` runs the whole studio
with no model server. See [EVALUATION.md](EVALUATION.md) for the real-model
validation attempt and why it was blocked here.

## Auth

### `401 unauthorized`
Get a token first. The demo service account is in `.env.example`:

```bash
curl -s -X POST localhost:8000/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"account_id":"marketer","password":"local-dev-password"}'
```

### `403 forbidden`
Valid token, missing scope. Creating a campaign needs `campaigns:write`; reading a
campaign or `/v1/usage` needs `campaigns:read`.

### App refuses to start in production
By design: `APP_ENV=production` with the default or a <32-char `JWT_SECRET` fails
fast at startup rather than booting insecurely.

## Generation

### My campaign came back but the copy looks templated
That's the **fallback path** working. If the model returns malformed JSON or errors
for a segment/channel slot, that slot degrades to a templated variant instead of
sinking the whole campaign (ADR-005). Check `generation_fallbacks_total` in
`/metrics` and look for `generation_failed` in the logs. In sandbox mode you should
see zero fallbacks. A nonzero count there means a real bug.

### I resubmitted the same brief and got the identical plan instantly
Working as intended (ADR-006). Briefs are fingerprinted; an identical brief returns
the cached plan rather than paying to regenerate it. `campaign_cache_hits_total`
increments. The fingerprint **includes the model label**, so switching
`LLM_MODE`/model produces a fresh generation rather than serving sandbox copy as if
it came from a real model. To force a regeneration, change any field in the brief.

### A variant I liked didn't win its segment
Check its guardrail flags. A **hard** flag (`sms_length`, `merge_tag`,
`banned_phrase`) drops a variant below clean ones in ranking; **soft** flags
(`subject_length`, `spam_trigger`, `all_caps`) are advisory and don't reorder
(ADR-007). The flags ride along on the scored variant in the response.

### `{first_name}` showed up literally / a merge tag got flagged
Only `{first_name}`, `{last_name}`, and `{product}` are supported. Anything else
trips the hard `merge_tag` rule, because an unknown tag would ship unrendered to a
real customer.

### Everything suddenly runs on the sandbox model
The daily budget cap tripped (ADR-004). `budget_cap_tripped_total` increments and
`GET /v1/usage` shows `"degraded": true`. Raise `DAILY_BUDGET_CAP_USD` if the cap is
too low, or look at what's burning spend first.

## State

### My campaigns disappeared after a restart
Expected. The store is **in-memory** (ADR-002). Campaigns, the brief cache, and the
daily spend counter all reset when the process restarts. That's a deliberate scope
choice for this project, not an oversight; the ADR explains the trade and what
swapping in a real store would take.

### Spend in `/v1/usage` looks lower than my provider bill
It's an **estimate at published per-token rates**, computed locally and reset on
restart, not a reconciled bill. Treat it as a guardrail signal, not accounting.

## Observability

### Grafana dashboard panels are empty
Expected until Prometheus has scraped a running instance that's actually done some
work. The dashboard is a correct definition, not a screenshot of invented traffic
(ADR-008). Bring it up with `docker compose --profile observability up` and generate
a few campaigns.
