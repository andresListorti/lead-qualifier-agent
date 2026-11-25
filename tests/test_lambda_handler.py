import pytest

from api.app.main import app
from api.lambda_handler import handler


@pytest.fixture(autouse=True)
def isolated_database(session_factory):
    # The module-level app reads .env; never depend on a local MySQL being up.
    # (Starlette's State is dynamic, so monkeypatch would delete it on undo.)
    original = app.state.session_factory
    app.state.session_factory = session_factory
    yield
    app.state.session_factory = original


def http_event(path: str) -> dict:
    """Minimal API Gateway HTTP API (payload v2) event."""
    return {
        "version": "2.0",
        "routeKey": "ANY /{proxy+}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "example.execute-api.us-east-1.amazonaws.com"},
        "requestContext": {
            "http": {
                "method": "GET", "path": path, "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1", "userAgent": "pytest",
            },
        },
        "isBase64Encoded": False,
    }


def test_lambda_handler_serves_health():
    response = handler(http_event("/health"), None)
    assert response["statusCode"] == 200
    assert "DEMO DATA" in response["body"]


def test_lambda_handler_protects_leads():
    response = handler(http_event("/leads"), None)
    assert response["statusCode"] in (401, 503)
