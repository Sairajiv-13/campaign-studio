# Deployment

The studio is a single stateless FastAPI process. There is no database, queue, or
worker to run (see [ADR-002](adr/002-in-memory-store.md)), so deployment is just
"run the container".

## Local / Docker Compose

The repo's [`docker-compose.yml`](../docker-compose.yml) brings the studio up in
sandbox mode, no API keys, no model download:

```bash
cp .env.example .env
docker compose up --build          # http://localhost:8000
```

Sign in at the UI with `marketer` / `local-dev-password`.

To generate with a **real** model, start the optional Ollama profile and flip the
mode:

```bash
docker compose --profile llm up -d ollama
docker compose exec ollama ollama pull llama3.1
LLM_MODE=real docker compose up --build
```

Any OpenAI-compatible endpoint works. Point `LLM_BASE_URL` at OpenAI, vLLM, or a
gateway and set `LLM_API_KEY`.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_ENV` | `local` | `local` \| `ci` \| `production`. Production enforces a strong `JWT_SECRET`. |
| `LOG_LEVEL` | `INFO` | Root log level; logs are structured JSON. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowlist. Never `*` in production. |
| `JWT_SECRET` | dev placeholder | **Required in production.** `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_ISSUER` | `campaign-studio` | Token `iss` claim. |
| `JWT_TTL_SECONDS` | `3600` | Access-token lifetime. |
| `SERVICE_ACCOUNT_ID` | `marketer` | Account that may mint tokens. |
| `SERVICE_ACCOUNT_PASSWORD` | `local-dev-password` | **Change in production.** Verified with bcrypt. |
| `RATE_LIMIT_REQUESTS` | `60` | Requests per window, per token/IP. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate-limit window. |
| `LLM_MODE` | `sandbox` | `sandbox` \| `real`. |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible endpoint. |
| `LLM_API_KEY` | `ollama` | Bearer token for that endpoint. |
| `LLM_MODEL` | `llama3.1` | Model id. |
| `LLM_TIMEOUT_SECONDS` | `60` | Per-request timeout (retried 3× with backoff). |
| `MAX_SEGMENTS` | `8` | Cap on segments per brief. |
| `MAX_VARIANTS_PER_SEGMENT` | `5` | Cap on variants per segment. |
| `MAX_REQUEST_BYTES` | `262144` | Bodies larger than this are rejected with 413. |

## Production considerations

- **Set the secrets.** `JWT_SECRET` and `SERVICE_ACCOUNT_PASSWORD` must be real
  values; the app refuses to boot in `APP_ENV=production` with the default secret.
- **Terminate TLS at the load balancer** and lock `CORS_ORIGINS` to your frontend.
- **Scale horizontally.** Generation is stateless and CPU/LLM-bound, so add
  replicas. Note that campaign *retrieval by id* is instance-local (ADR-002). Put
  a shared store behind `CampaignStore` if you need cross-replica reads.
- **Rate limiting is per-process.** With N replicas the effective limit is N× the
  configured value; move it to a shared store if you need a global budget.
- **Scrape `/metrics`.** It exposes `llm_calls_total`, `llm_latency_seconds`, and
  `campaign_generations_total`. Alert on LLM error rate and p99 latency. With a
  real model, latency is dominated by the model call.
- **Watch LLM cost and rate limits.** Each campaign issues one generate call per
  segment×channel plus one judge call per variant; budget accordingly.
- **Keep `/metrics` internal**. It is unauthenticated for scrapers; gate it at the
  ingress or bind it to a private network.
- **Health checks:** point the load balancer at `GET /health`.

## Terraform sketch (ECS Fargate + RDS)

Illustrative only. The studio needs no database today; RDS is shown for the case
where you swap `CampaignStore` for Postgres.

```hcl
resource "aws_ecs_task_definition" "studio" {
  family                   = "campaign-studio"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn

  container_definitions = jsonencode([{
    name      = "studio"
    image     = "${aws_ecr_repository.studio.repository_url}:latest"
    portMappings = [{ containerPort = 8000 }]
    environment = [
      { name = "APP_ENV",  value = "production" },
      { name = "LLM_MODE", value = "real" },
    ]
    secrets = [
      { name = "JWT_SECRET", valueFrom = aws_secretsmanager_secret.jwt.arn },
      { name = "LLM_API_KEY", valueFrom = aws_secretsmanager_secret.llm.arn },
    ]
  }])
}

resource "aws_ecs_service" "studio" {
  name            = "campaign-studio"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.studio.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  load_balancer {
    target_group_arn = aws_lb_target_group.studio.arn
    container_name   = "studio"
    container_port   = 8000
  }
}

# Only needed if CampaignStore is swapped for Postgres.
resource "aws_db_instance" "studio" {
  identifier     = "campaign-studio"
  engine         = "postgres"
  instance_class = "db.t4g.micro"
  allocated_storage = 20
  skip_final_snapshot = true
}
```
