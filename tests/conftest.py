import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent import FixtureProvider
from api.app.config import Settings
from api.app.database import Base
from api.app.main import create_app

DOMAIN = "test-tenant.us.auth0.com"
AUDIENCE = "https://lead-qualifier-api"

VALID_LEAD = {
    "name": "DEMO DATA Person",
    "company": "DEMO DATA Company",
    "message": "We would like a demo meeting, this is urgent.",
    "budget": "6000",
}


def _new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def signing_key():
    return _new_key()


@pytest.fixture(scope="session")
def other_key():
    return _new_key()


def make_token(key, **overrides):
    """Build a signed test token. Passing a claim as None removes it."""
    claims = {
        "iss": f"https://{DOMAIN}/",
        "aud": AUDIENCE,
        "sub": "test-client@clients",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "permissions": ["read:leads"],
    }
    for name, value in overrides.items():
        if value is None:
            claims.pop(name, None)
        else:
            claims[name] = value
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def make_client(session_factory, signing_key):
    def build(**settings_overrides):
        values = {"auth0_domain": DOMAIN, "auth0_audience": AUDIENCE, **settings_overrides}
        app = create_app(
            Settings(database_url="sqlite://", **values),
            session_factory=session_factory,
            provider=FixtureProvider(),
            key_resolver=lambda _token: signing_key.public_key(),
        )
        return TestClient(app)

    return build


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def auth_headers(signing_key):
    return {"Authorization": f"Bearer {make_token(signing_key)}"}
