"""Unit tests for JWT minting/verification."""

from __future__ import annotations

import datetime as dt

import pytest
from app.errors import AuthenticationError
from app.security.jwt import create_access_token, decode_token

SECRET = "unit-secret"
ISSUER = "campaign-studio"


def _token(**over: object) -> str:
    params: dict[str, object] = {
        "subject": "marketer",
        "scopes": ["campaigns:write"],
        "secret": SECRET,
        "issuer": ISSUER,
        "ttl_seconds": 3600,
    }
    params.update(over)
    return create_access_token(**params)  # type: ignore[arg-type]


def test_roundtrip() -> None:
    principal = decode_token(_token(), secret=SECRET, issuer=ISSUER)
    assert principal.subject == "marketer"
    assert "campaigns:write" in principal.scopes


def test_expired_rejected() -> None:
    past = dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)
    with pytest.raises(AuthenticationError):
        decode_token(_token(ttl_seconds=1, now=past), secret=SECRET, issuer=ISSUER)


def test_wrong_secret_rejected() -> None:
    with pytest.raises(AuthenticationError):
        decode_token(_token(), secret="other", issuer=ISSUER)


def test_wrong_issuer_rejected() -> None:
    with pytest.raises(AuthenticationError):
        decode_token(_token(), secret=SECRET, issuer="someone-else")
