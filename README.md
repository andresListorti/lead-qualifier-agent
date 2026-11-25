# Lead Qualifier Agent

**English** | [Español](README.es.md)

[![CI](https://github.com/andresListorti/lead-qualifier-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/andresListorti/lead-qualifier-agent/actions/workflows/ci.yml)

> **Portfolio project — DEMO DATA only — not a production system.**

A small FastAPI service that receives sales leads, qualifies them with an AI agent
(score + tier: `hot` / `warm` / `cold`), stores them in MySQL, and exposes them through an
API protected by Auth0 (JWT, RS256, RBAC).

Built to show a realistic backend stack end to end: FastAPI, Pydantic v2, SQLAlchemy 2,
Alembic, MySQL, Auth0, GitHub Actions, and AWS Lambda packaging (ready, not deployed by decision).

## Two ways to see it

The same running API offers two views; each links to the other.

| View | URL | For |
| --- | --- | --- |
| **Simple view** | `http://127.0.0.1:8000/` | Anyone: a form, a colored result (hot / warm / cold), one-click checks (idempotency, validation, auth) and an "Under the hood" log of every real HTTP call with headers, body and a curl equivalent. ES / EN and light / dark toggles. |
| **Technical view** | `http://127.0.0.1:8000/docs` | Engineers: Swagger UI generated from the OpenAPI schema, including the Auth0 `Authorize` flow. |

The simple view (`web/index.html`) is a dependency-free page and a plain client of the public
endpoints; it adds no API surface and is excluded from the OpenAPI schema.

## Stack

| Area | Choice |
| --- | --- |
| API | Python 3.13, FastAPI, Pydantic v2 |
| Data | MySQL 8 (Docker), SQLAlchemy 2, Alembic migrations |
| Auth | Auth0 access tokens, RS256 validated against the tenant JWKS |
| Agent | `LLMProvider` protocol: deterministic fixture provider (default) or optional Gemini free tier |
| CI | GitHub Actions: ruff, pytest, migrations + seed against a MySQL service container |
| Tests | pytest, SQLite, 62 tests |

## Endpoints

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/health` | public | Liveness + database check |
| POST | `/leads` | public | Create + qualify (201); optional Idempotency-Key replay (200); IP rate limit (429) |
| GET | `/leads` | `read:leads` | List leads (`offset`, `limit` ≤ 100) |
| GET | `/leads/{id}` | `read:leads` | Get one lead |

Interactive docs at `/docs` and the simple view at `/` when the server is running.

## Reliability

`POST /leads` accepts an optional `Idempotency-Key` header: 1-100 ASCII letters,
digits, underscores or hyphens; invalid keys return `422`. A new key creates a lead
with `201`; replaying a stored key returns the original lead with `200` without
calling the agent again, even if the submitted payload changed. Keys are global
and retained with the lead; use a fresh key for each intended new lead. Without
a key, each request creates a new lead. Run `alembic upgrade head` to apply migration
`0002` (nullable `VARCHAR(100)` plus a unique index).

The unique index resolves concurrent inserts: on a commit conflict the session
rolls back and returns the winning row with `200`. Two overlapping requests can
both qualify before either commits; this guarantees one stored lead per key,
not exactly-once provider execution during a race.

`RATE_LIMIT_PER_MINUTE` defaults to `30`; `0` disables it. A thread-safe in-memory
fixed window limits POST requests per client IP, returning `429` with `Retry-After`
in seconds. Replays and rejected requests also consume the quota. GET endpoints
are unaffected. The limiter uses the ASGI client address; proxy configuration
must supply the correct client IP (raw forwarded headers are not trusted here).

**Per-process only:** restarts clear counters and Lambda/several instances do not
share them. In production, throttling would live in API Gateway or Redis. This
portfolio implementation is not a distributed production limit.

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

`qualify_lead` asks an `LLMProvider` for `{tier, score, reasons, suggested_reply}`, validates it
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

## AWS (serverless, ready but not deployed)

`api/lambda_handler.py` wraps the FastAPI app with Mangum, and `template.yaml` (AWS SAM)
defines one Lambda function behind an API Gateway HTTP API. There is no RDS, EC2, NAT or load
balancer: `DATABASE_URL` points to an external MySQL and is passed as a `NoEcho` parameter.
The template is linted with `cfn-lint` in CI and the handler is covered by tests.
This repo has **not** been deployed to AWS; it is prepared for it.

```bash
sam build
sam local start-api          # runs Lambda + API Gateway locally in Docker
```

## Roadmap

- [x] Phase 1: API, MySQL, migrations, agent, tests
- [x] Phase 2: Auth0 JWT validation with RBAC
- [x] Phase 3: CI with GitHub Actions
- [x] Phase 4a: AWS-ready: Lambda handler (Mangum) + SAM template (Lambda + HTTP API), linted in CI. **Not deployed** (not deployed by decision)
- [x] Reliability demo: idempotent lead creation + per-process IP rate limiting
- [ ] Phase 4b: real deployment to the AWS free plan, GitHub OIDC (no long-lived keys)
- [x] Simple view at `/`: a plain HTML client of the API, bilingual (ES / EN)
- [ ] Optional: full Next.js frontend

## License

MIT
