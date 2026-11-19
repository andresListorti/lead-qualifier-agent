from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.app.agent import LLMProvider, make_provider, qualify_lead
from api.app.auth import KeyResolver, make_jwks_resolver, require_read_leads
from api.app.config import Settings
from api.app.database import make_engine, make_session_factory
from api.app.models import Lead
from api.app.schemas import LeadCreate, LeadRead


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def get_provider(request: Request) -> LLMProvider:
    return request.app.state.provider


SessionDep = Annotated[Session, Depends(get_session)]
ProviderDep = Annotated[LLMProvider, Depends(get_provider)]


def create_app(
    settings: Settings | None = None, *, session_factory=None, provider=None,
    key_resolver: KeyResolver | None = None,
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
    app.state.auth = None
    if settings.auth0_domain and settings.auth0_audience:
        app.state.auth = {
            "domain": settings.auth0_domain,
            "audience": settings.auth0_audience,
            "resolver": key_resolver or make_jwks_resolver(settings.auth0_domain),
        }

    @app.get("/health")
    def health(session: SessionDep):
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="Database unavailable") from None
        return {"status": "ok", "data_label": "DEMO DATA"}

    @app.post("/leads", response_model=LeadRead, status_code=201)
    def create_lead(payload: LeadCreate, session: SessionDep, provider: ProviderDep):
        result = qualify_lead(payload, provider)
        lead = Lead(**payload.model_dump(), qualification=result.model_dump())
        session.add(lead)
        session.commit()
        session.refresh(lead)
        return lead

    @app.get("/leads", response_model=list[LeadRead], dependencies=[Depends(require_read_leads)])
    def list_leads(
        session: SessionDep,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ):
        return session.scalars(select(Lead).order_by(Lead.id).offset(offset).limit(limit)).all()

    @app.get(
        "/leads/{lead_id}", response_model=LeadRead, dependencies=[Depends(require_read_leads)]
    )
    def get_lead(lead_id: int, session: SessionDep):
        lead = session.get(Lead, lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead

    return app


app = create_app()
