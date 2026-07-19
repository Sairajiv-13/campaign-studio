"""FastAPI auth dependencies and password hashing."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import bcrypt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.errors import AuthenticationError, AuthorizationError
from app.security.jwt import Principal, decode_token

SCOPE_CAMPAIGNS_WRITE = "campaigns:write"
SCOPE_CAMPAIGNS_READ = "campaigns:read"

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing bearer token")
    return decode_token(
        credentials.credentials, secret=settings.jwt_secret, issuer=settings.jwt_issuer
    )


def require_scope(scope: str) -> Callable[[Principal], Awaitable[Principal]]:
    async def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if scope not in principal.scopes:
            raise AuthorizationError(f"Token is missing required scope '{scope}'")
        return principal

    return dependency
