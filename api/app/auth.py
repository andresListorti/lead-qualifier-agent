"""Auth0 access-token validation (RS256) for protected endpoints.

Security rules implemented here:
- Only RS256 is accepted (the algorithm is pinned, never read from the token header).
- Signature is checked against Auth0's JWKS; `iss`, `aud` and `exp` are mandatory and verified.
- Access is granted only if the token carries the required permission (RBAC `permissions`
  claim, or the space-separated `scope` claim).
- Missing/invalid token -> 401. Valid token without the permission -> 403.
- If Auth0 is not configured, protected endpoints fail closed (503), never open.
"""

from collections.abc import Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWTError

ALGORITHMS = ["RS256"]
READ_LEADS = "read:leads"

# Given a raw JWT string, return the public key that must verify it.
KeyResolver = Callable[[str], Any]

bearer_scheme = HTTPBearer(auto_error=False, description="Auth0 access token")


def make_jwks_resolver(domain: str) -> KeyResolver:
    """Resolve signing keys from Auth0's JWKS endpoint (keys are cached by PyJWKClient)."""
    client = PyJWKClient(
        f"https://{domain}/.well-known/jwks.json", cache_keys=True, lifespan=3600, timeout=5
    )

    def resolve(token: str) -> Any:
        return client.get_signing_key_from_jwt(token).key

    return resolve


def issuer_for(domain: str) -> str:
    return f"https://{domain}/"


def _permissions(claims: dict) -> set[str]:
    # Malformed claim types grant nothing (and never crash with a 500).
    permissions = claims.get("permissions")
    granted: set[str] = set()
    if isinstance(permissions, list):
        granted.update(p for p in permissions if isinstance(p, str))
    scope = claims.get("scope")
    if isinstance(scope, str):
        granted.update(scope.split())
    return granted


def _unauthorized() -> HTTPException:
    # One generic message: never reveal why validation failed.
    return HTTPException(
        status_code=401, detail="Invalid or missing token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_token(token: str, *, resolver: KeyResolver, domain: str, audience: str) -> dict:
    try:
        key = resolver(token)
        return jwt.decode(
            token,
            key,
            algorithms=ALGORITHMS,
            audience=audience,
            issuer=issuer_for(domain),
            options={"require": ["exp", "iss", "aud"]},
        )
    except PyJWKClientConnectionError:
        raise HTTPException(status_code=503, detail="Identity provider unavailable") from None
    except PyJWTError:
        raise _unauthorized() from None


def require_permission(permission: str):
    def dependency(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    ) -> dict:
        auth = request.app.state.auth
        if auth is None:
            raise HTTPException(status_code=503, detail="Authentication is not configured")
        if credentials is None:
            raise _unauthorized()
        claims = verify_token(
            credentials.credentials,
            resolver=auth["resolver"], domain=auth["domain"], audience=auth["audience"],
        )
        if permission not in _permissions(claims):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return claims

    return dependency


require_read_leads = require_permission(READ_LEADS)
