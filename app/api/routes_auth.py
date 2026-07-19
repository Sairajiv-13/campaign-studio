"""Authentication endpoint: exchange service credentials for a JWT."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.schemas import TokenRequest, TokenResponse
from app.config import Settings, get_settings
from app.deps import enforce_rate_limit, get_container
from app.errors import AuthenticationError
from app.security.auth import (
    SCOPE_CAMPAIGNS_READ,
    SCOPE_CAMPAIGNS_WRITE,
    verify_password,
)
from app.security.jwt import create_access_token

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def issue_token(
    payload: TokenRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    _: None = Depends(enforce_rate_limit),
) -> TokenResponse:
    container = get_container(request)
    ok = payload.account_id == container.service_account_id and verify_password(
        payload.password, container.service_account_password_hash
    )
    if not ok:
        raise AuthenticationError("Invalid credentials")

    token = create_access_token(
        subject=container.service_account_id,
        scopes=[SCOPE_CAMPAIGNS_WRITE, SCOPE_CAMPAIGNS_READ],
        secret=settings.jwt_secret,
        issuer=settings.jwt_issuer,
        ttl_seconds=settings.jwt_ttl_seconds,
    )
    return TokenResponse(access_token=token, expires_in=settings.jwt_ttl_seconds)
