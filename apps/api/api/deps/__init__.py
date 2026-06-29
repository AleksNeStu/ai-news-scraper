"""Shared FastAPI dependencies.

Single source of truth for cross-router dependency callables:
    * ``AUTH_COOKIE_NAME`` — the HTTP-only cookie that carries the JWT.
    * ``get_current_user_id`` — Bearer-or-cookie JWT decoder that
      resolves to the authenticated user's UUID (or raises 401).

Kept thin on purpose: routers call these, but anything heavy lives in
``api.services.auth``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.services.auth import decode_token

AUTH_COOKIE_NAME = "ai_news_auth"
_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Pull the JWT from the Authorization header or the auth cookie."""
    if bearer is not None and bearer.scheme.lower() == "bearer":
        return bearer.credentials
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_id(token: str = Depends(_extract_token)) -> UUID:
    """Resolve the JWT to a user UUID or raise 401."""
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return UUID(str(sub))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is not a UUID",
        ) from exc


__all__ = ["AUTH_COOKIE_NAME", "get_current_user_id"]
