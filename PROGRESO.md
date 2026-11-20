# Progress

## Phase 1: FastAPI + SQL + qualification agent (fixture mode) — done
- `api/app/`: FastAPI app, SQLAlchemy 2 models, Pydantic v2 schemas, Alembic migration.
- Endpoints: `GET /health`, `POST /leads` (creates and qualifies), `GET /leads`, `GET /leads/{id}`.
- Agent: `LLMProvider` interface with a deterministic `FixtureProvider` (default, offline) and an
  optional `GeminiProvider`. Output is validated by Pydantic; one retry, then a safe fallback.
- Seed: 10 fictional leads labeled `DEMO DATA`.
- Tests: `pytest` (18 passing, SQLite in memory, no Docker needed). Lint: `ruff` clean.

## How to run locally
```
python -m venv .venv && .venv\Scripts\activate
pip install fastapi sqlalchemy alembic pymysql cryptography uvicorn httpx python-dotenv pytest ruff
set DATABASE_URL=sqlite:///./leads.db
alembic upgrade head
python -m api.app.seed
uvicorn api.app.main:app --reload     # Swagger UI at /docs
pytest && ruff check .
```

## Next
- Phase 2: Auth0 JWT validation (RS256, JWKS, `read:leads` scope) on `GET` endpoints.
- Phase 3: GitHub Actions (ruff, pytest with MySQL service container).
- Phase 4: AWS Lambda + API Gateway (SAM), deployed with GitHub OIDC.
- Phase 5: README with architecture notes.

*Portfolio project — DEMO DATA only — not a production system.*

## Update: Phases 2 and 3 done

- Phase 2: Auth0 RS256 JWT validation with RBAC (`read:leads`) on `GET /leads` and `GET /leads/{id}`; fails closed. 38 tests.
- Phase 3: GitHub Actions CI (ruff, pytest, Alembic migrations + seed against a MySQL service container).
- Next: test with a real Auth0 token, then AWS (Phase 4).


## Update 2026-11-20: reliability demo

- `POST /leads`: optional validated `Idempotency-Key`; new leads return 201,
  stored-key replays return the original lead with 200 without calling the provider.
- Migration `0002`: nullable VARCHAR(100) with a unique index; `0001` unchanged.
  Commit conflicts roll back and retrieve the winning row. Concurrent requests
  may both call the provider before the winning commit; no exactly-once claim.
- `api/app/ratelimit.py`: thread-safe fixed-window dependency by client IP,
  injected monotonic clock, `RATE_LIMIT_PER_MINUTE=30` by default, 0 disables;
  429 responses include Retry-After. State is per-process only; production across
  Lambda/instances would require API Gateway throttling or Redis.
- Validation: baseline 40 tests; updated suite 55 tests passing; `ruff check .` clean.
  Added replay/provider-count, distinct/no keys, invalid/boundary keys, actual
  unique-index conflict recovery, unrelated integrity errors, per-IP isolation,
  clock-driven reset, disabled limit, env configuration, and migration
  upgrade/downgrade with an existing demo row (SQLite).
- MySQL runtime and AWS deployment were not tested in this update; AWS remains
  not deployed by decision. No packages added, secrets changed, or push performed.

*Portfolio project — DEMO DATA only — not a production system.*
