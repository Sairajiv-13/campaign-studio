# 2. Campaigns live in an in-memory store

- Status: Accepted
- Date: 2026-07-20

## Context

Generated campaign plans need to be retrievable by id (`GET /v1/campaigns/{id}`).
The obvious reflex is to add PostgreSQL. But this project's value is the
**generation and scoring engine**, not CRUD or durability. Adding a database would
mean a schema, migrations, a connection pool, a container in compose, and a test
fixture. Infrastructure that carries real cost and demonstrates nothing the
scorer doesn't already demonstrate.

## Decision

Campaign plans are stored in a process-local `CampaignStore` (`app/store.py`): a
dict behind a small interface (`save`, `get`, `count`) with a lock for safety.

The **interface is the seam**. Swapping in Postgres or Redis means implementing
those three methods; the API and pipeline are untouched because neither reaches
past the store.

## Consequences

- Zero infrastructure: no database container, no migrations, no ORM, no fixtures.
  The test suite is fully hermetic and the image is small.
- **Campaigns do not survive a restart, and do not exist across replicas.** This is
  an explicit, documented limitation, not an oversight. Generation is stateless, so
  the API still scales horizontally. Only retrieval-by-id is instance-local.
- If persistence is needed later, it is a contained change behind `CampaignStore`
  rather than a refactor.
