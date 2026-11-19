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
