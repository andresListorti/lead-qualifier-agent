import base64
import hashlib
import hmac
import json

import pytest
from cryptography.hazmat.primitives import serialization

from tests.conftest import AUDIENCE, DOMAIN, make_token


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_health_and_post_leads_stay_public(client):
    assert client.get("/health").status_code == 200
    body = {"name": "DEMO DATA A", "company": "DEMO DATA B", "message": "hi", "budget": "10"}
    assert client.post("/leads", json=body).status_code == 201


@pytest.mark.parametrize("path", ["/leads", "/leads/1"])
def test_protected_routes_require_a_token(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_valid_token_with_permission_is_accepted(client, signing_key):
    assert client.get("/leads", headers=bearer(make_token(signing_key))).status_code == 200


def test_scope_claim_is_also_accepted(client, signing_key):
    token = make_token(signing_key, permissions=None, scope="openid read:leads")
    assert client.get("/leads", headers=bearer(token)).status_code == 200


def test_valid_token_without_permission_is_forbidden(client, signing_key):
    token = make_token(signing_key, permissions=["write:leads"])
    assert client.get("/leads", headers=bearer(token)).status_code == 403


def test_token_without_any_permission_is_forbidden(client, signing_key):
    token = make_token(signing_key, permissions=None)
    assert client.get("/leads", headers=bearer(token)).status_code == 403


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": 1},  # expired
        {"aud": "https://some-other-api"},  # wrong audience
        {"iss": "https://evil.example.com/"},  # wrong issuer
        {"exp": None},  # missing exp
        {"aud": None},  # missing aud
        {"iss": None},  # missing iss
    ],
)
def test_bad_claims_are_rejected(client, signing_key, overrides):
    token = make_token(signing_key, **overrides)
    assert client.get("/leads", headers=bearer(token)).status_code == 401


def test_token_signed_with_another_key_is_rejected(client, other_key):
    assert client.get("/leads", headers=bearer(make_token(other_key))).status_code == 401


def test_garbage_and_none_algorithm_tokens_are_rejected(client):
    header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    claims = {
        "iss": f"https://{DOMAIN}/", "aud": AUDIENCE, "exp": 9999999999,
        "permissions": ["read:leads"],
    }
    payload = b64(json.dumps(claims).encode())
    assert client.get("/leads", headers=bearer(f"{header}.{payload}.")).status_code == 401
    assert client.get("/leads", headers=bearer("not-a-jwt")).status_code == 401


def test_hs256_token_signed_with_public_key_is_rejected(client, signing_key):
    """Algorithm-confusion attack: an HS256 token HMAC'd with the public key must fail."""
    public_pem = signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    claims = {
        "iss": f"https://{DOMAIN}/", "aud": AUDIENCE, "exp": 9999999999,
        "permissions": ["read:leads"],
    }
    head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(json.dumps(claims).encode())
    sig = b64(hmac.new(public_pem, f"{head}.{body}".encode(), hashlib.sha256).digest())
    assert client.get("/leads", headers=bearer(f"{head}.{body}.{sig}")).status_code == 401


def test_auth_not_configured_fails_closed(make_client, signing_key):
    unconfigured = make_client(auth0_domain="", auth0_audience="")
    response = unconfigured.get("/leads", headers=bearer(make_token(signing_key)))
    assert response.status_code == 503
