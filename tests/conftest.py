import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent import FixtureProvider
from api.app.config import Settings
from api.app.database import Base
from api.app.main import create_app


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(session_factory):
    app = create_app(
        Settings(database_url="sqlite://"),
        session_factory=session_factory,
        provider=FixtureProvider(),
    )
    return TestClient(app)


VALID_LEAD = {
    "name": "DEMO DATA Person",
    "company": "DEMO DATA Company",
    "message": "We would like a demo meeting, this is urgent.",
    "budget": "6000",
}
