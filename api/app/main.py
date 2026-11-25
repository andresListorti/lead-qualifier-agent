from collections.abc import Callable
from time import monotonic
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from api.app.agent import LLMProvider, make_provider, qualify_lead
from api.app.auth import KeyResolver, make_jwks_resolver, require_read_leads
from api.app.config import Settings
from api.app.database import make_engine, make_session_factory
from api.app.models import Lead
from api.app.ratelimit import RateLimiter, rate_limit
from api.app.schemas import LeadCreate, LeadRead


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def get_provider(request: Request) -> LLMProvider:
    return request.app.state.provider


AUTH_RESPONSES = {
    401: {"description": "Missing or invalid token"},
    403: {"description": "Token lacks read:leads"},
    503: {"description": "Authentication not configured or identity provider unavailable"},
}

SessionDep = Annotated[Session, Depends(get_session)]
ProviderDep = Annotated[LLMProvider, Depends(get_provider)]


def create_app(
    settings: Settings | None = None, *, session_factory=None, provider=None,
    key_resolver: KeyResolver | None = None,
    clock: Callable[[], float] = monotonic,
) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="Lead Qualifier Agent",
        description=(
            "Portfolio project — DEMO DATA only. "
            "GET endpoints require an Auth0 token with read:leads."
        ),
    )
    app.state.session_factory = (
        session_factory if session_factory is not None
        else make_session_factory(make_engine(settings.database_url))
    )
    app.state.provider = provider if provider is not None else make_provider(settings)
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute, clock=clock)
    app.state.auth = None
    if settings.auth0_domain and settings.auth0_audience:
        app.state.auth = {
            "domain": settings.auth0_domain,
            "audience": settings.auth0_audience,
            "resolver": key_resolver or make_jwks_resolver(settings.auth0_domain),
        }

    @app.get("/health", responses={503: {"description": "Database unavailable"}})
    def health(session: SessionDep):
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="Database unavailable") from None
        return {"status": "ok", "data_label": "DEMO DATA"}

    @app.post(
        "/leads", response_model=LeadRead, status_code=201,
        dependencies=[Depends(rate_limit)],
        responses={200: {"model": LeadRead, "description": "Idempotent replay"},
                   429: {"description": "Rate limit exceeded; see Retry-After"}},
    )
    def create_lead(
        payload: LeadCreate, session: SessionDep, provider: ProviderDep, response: Response,
        idempotency_key: Annotated[
            str | None, Header(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
        ] = None,
    ):
        if idempotency_key is not None:
            existing = session.scalar(select(Lead).where(Lead.idempotency_key == idempotency_key))
            if existing is not None:
                response.status_code = 200
                return existing
        result = qualify_lead(payload, provider)
        lead = Lead(
            **payload.model_dump(), qualification=result.model_dump(),
            idempotency_key=idempotency_key,
        )
        session.add(lead)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if idempotency_key is not None:
                existing = session.scalar(
                    select(Lead).where(Lead.idempotency_key == idempotency_key)
                )
                if existing is not None:
                    response.status_code = 200
                    return existing
            raise
        session.refresh(lead)
        return lead

    @app.get(
        "/leads", response_model=list[LeadRead], dependencies=[Depends(require_read_leads)],
        responses=AUTH_RESPONSES,
    )
    def list_leads(
        session: SessionDep,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ):
        return session.scalars(select(Lead).order_by(Lead.id).offset(offset).limit(limit)).all()

    @app.get(
        "/leads/{lead_id}", response_model=LeadRead, dependencies=[Depends(require_read_leads)],
        responses={**AUTH_RESPONSES, 404: {"description": "Lead not found"}},
    )
    def get_lead(lead_id: int, session: SessionDep):
        lead = session.get(Lead, lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead

    return app


app = create_app()
