# Lead Qualifier Agent

[![CI](https://github.com/andresListorti/lead-qualifier-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/andresListorti/lead-qualifier-agent/actions/workflows/ci.yml)

> **Portfolio project — DEMO DATA only — not a production system.**

A small FastAPI service that receives sales leads, qualifies them with an AI agent
(score + tier: `hot` / `warm` / `cold`), stores them in MySQL, and exposes them through an
API protected by Auth0 (JWT, RS256, RBAC).

Built to show a realistic backend stack end to end: FastAPI, Pydantic v2, SQLAlchemy 2,
Alembic, MySQL, Auth0, GitHub Actions, and (next) AWS Lambda.

## Stack

| Area | Choice |
| --- | --- |
| API | Python 3.13, FastAPI, Pydantic v2 |
| Data | MySQL 8 (Docker), SQLAlchemy 2, Alembic migrations |
| Auth | Auth0 access tokens, RS256 validated against the tenant JWKS |
| Agent | `LLMProvider` protocol: deterministic fixture provider (default) or optional Gemini free tier |
| CI | GitHub Actions: ruff, pytest, migrations + seed against a MySQL service container |
| Tests | pytest, SQLite in memory, 38 tests |

## Endpoints

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/health` | public | Liveness + database check |
| POST | `/leads` | public | Create a lead; the agent qualifies it on the way in |
| GET | `/leads` | `read:leads` | List leads (`offset`, `limit` ≤ 100) |
| GET | `/leads/{id}` | `read:leads` | Get one lead |

Interactive docs at `/docs` when the server is running.

## Security design

- Only **RS256** is accepted; the algorithm is pinned in code, never read from the token header.
- Signature verified against Auth0's JWKS (cached); `iss`, `aud` and `exp` are required.
- Permission is read from the RBAC `permissions` claim (or `scope`); malformed claim types grant nothing.
- Missing/invalid token → `401`; valid token without permission → `403`;
  Auth0 not configured or unreachable → `503` (**fails closed**, never open).
- Generic error messages: the API never reveals why a token was rejected.
- Tests cover algorithm confusion (HS256 signed with the public key), `alg=none`, wrong key,
  wrong audience/issuer, expired and missing claims.
- No secrets in the repo: configuration comes from environment variables (`.env.example`).

## The agent

`qualify_lead` asks an `LLMProvider` for `{score, tier, reason}`, validates it
(the tier must match the score: hot ≥ 70, warm ≥ 40, otherwise cold), retries once, and
falls back to a safe result if the provider fails or answers inconsistently.

- `FixtureProvider` (default): deterministic rules, no network, no cost. Used in tests and CI.
- `GeminiProvider` (optional): only active with `GEMINI_API_KEY` **and**
  `GEMINI_FREE_TIER_CONFIRMED=true`, so it cannot spend money by accident.

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install fastapi pydantic sqlalchemy alembic pymysql cryptography "pyjwt[crypto]" \
    uvicorn httpx python-dotenv pytest ruff
cp .env.example .env            # then set the MySQL passwords
docker compose up -d            # MySQL 8 on 127.0.0.1:3306
alembic upgrade head
python -m api.app.seed          # 10 DEMO DATA leads (idempotent)
uvicorn api.app.main:app --reload
```

Run the checks:

```bash
ruff check .
pytest -q
```

To call the protected endpoints, create an Auth0 API with the `read:leads` permission,
set `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` in `.env`, and send an access token as
`Authorization: Bearer <token>`.

## Roadmap

- [x] Phase 1: API, MySQL, migrations, agent, tests
- [x] Phase 2: Auth0 JWT validation with RBAC
- [x] Phase 3: CI with GitHub Actions
- [ ] Phase 4: AWS deployment (Lambda + API Gateway via SAM, GitHub OIDC, no long-lived keys)
- [ ] Optional: small Next.js frontend

## License

MIT
