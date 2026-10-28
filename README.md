# TaskFlow API

Production-oriented **asynchronous job processing API** built with FastAPI, PostgreSQL, RabbitMQ, SQLAlchemy and Docker Compose.

> Portfolio project: demonstrates backend engineering patterns; not represented as commercial production experience.

## Architecture

```text
Client --API key--> FastAPI --SQLAlchemy--> PostgreSQL
                      |                    ^
                      v                    |
                   RabbitMQ ---> Worker ---+
```

Jobs support `word_count` and `checksum` (SHA-256). Processing is performed by a separate worker, not inside the HTTP request. Durable RabbitMQ messages, PostgreSQL row locks, job event history, retry limits, API key authentication and idempotent submission are included.

## Quick start

Requires Docker with Compose and internet access to pull images/build dependencies.

```bash
cp .env.example .env
# Edit .env: set a random API_KEY and POSTGRES_PASSWORD
docker compose up --build -d
```

Swagger: http://localhost:8003/docs
RabbitMQ management: http://localhost:15672 (guest / guest; bound to localhost only)

### Demo

```bash
curl -i -X POST http://localhost:8003/v1/jobs \
  -H 'X-API-Key: YOUR_API_KEY_FROM_ENV' \
  -H 'Idempotency-Key: example-job-0001' \
  -H 'Content-Type: application/json' \
  -d '{"operation":"word_count","text":"FastAPI worker handles jobs"}'
```

Use the returned `id` with `GET /v1/jobs/{id}` and `GET /v1/jobs/{id}/events` (include `X-API-Key`). In Swagger, provide the `X-API-Key` header in the endpoint parameters.

## Recovery and guarantees

If RabbitMQ is unavailable *after* a job is committed, API returns HTTP 503 with a job ID and leaves the job `pending`. To republish pending jobs:

```bash
docker compose exec api python -m app.recover
```

**Delivery is at least once**, not exactly once. Duplicate queue deliveries are safe for finalized jobs, enforced using a PostgreSQL row lock. Retried jobs may be delivered more than once. Processing is deterministic and results are stored in PostgreSQL.

**Limitations:** recovery is manual (not a transactional outbox); initial database schema is created with `create_all` rather than versioned Alembic migrations; there is no production-grade metrics, tracing, rate limiting, distributed scheduler, or secret manager. Intended for local demonstration, not internet-facing deployment without hardening.

## Tests and lint

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
ruff check .
```

Tests use an isolated in-memory SQLite database and mock RabbitMQ. PostgreSQL/RabbitMQ integration must additionally be verified with Docker Compose. GitHub Actions runs unit/API tests and lint on pushes.

## Endpoints

- `GET /health/live` — liveness
- `POST /v1/jobs` — submit with `Idempotency-Key` and `X-API-Key`
- `GET /v1/jobs` — recent jobs
- `GET /v1/jobs/{id}` — job status/result
- `GET /v1/jobs/{id}/events` — audit trail

## Security

- Set a unique `API_KEY` and `POSTGRES_PASSWORD` in `.env`; never commit it.
- API and management UI bind to `127.0.0.1` by default.
- This is a local demo: the RabbitMQ management account uses default credentials, so do not expose it publicly.
