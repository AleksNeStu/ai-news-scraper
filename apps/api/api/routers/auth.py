"""Auth router — register, login, refresh, logout, me.

Per ADR-015:
    * H1 (handled in schemas/auth.py) — mass-assignment guard via
      ``extra="forbid"`` on UserCreate / UserLogin.
    * H2 — ``/auth/login`` is gated by ``rate_limit_ip("login", ...)``
      at 10 hits / 60s / IP. ``/auth/register`` keeps its existing
      5/3600 limit.
    * H3 — server-side logout invalidation via the refresh-token
      table. ``/auth/login`` and ``/auth/register`` set both the
      short-lived JWT cookie and the long-lived opaque refresh
      cookie. ``/auth/logout`` revokes the refresh row and clears
      both cookies. ``/auth/refresh`` rotates a refresh row into a
      new pair.
"""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.db.database import get_db
from api.deps import (
    AUTH_COOKIE_NAME,
    AUTH_REFRESH_COOKIE_NAME,
    get_current_user_id,
)
from api.exceptions import AuthenticationError
from api.middleware.rate_limit import rate_limit_ip
from api.models.user import User
from api.schemas.auth import AuthResponse, UserCreate, UserLogin, UserOut
from api.services.auth import (
    create_refresh_token,
    create_token,
    hash_password,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


# ---------------------------------------------------------------------------
# Cookie helpers — ADR-015 §15.9 contract.
#
# Both set / both clear share the SAME flag tuple (HttpOnly, env-gated
# Secure, SameSite=Lax, path="/"). ``delete_cookie`` is called with the
# matching flags so the browser attributes match — this also closes the
# M3 cosmetic finding (asymmetric ``delete_cookie``) from the ADR.
# ---------------------------------------------------------------------------


def _set_auth_cookies(
    response: Response, *, access: str, refresh: str
) -> None:
    is_prod = _settings.app_env == "production"
    response.set_cookie(
        AUTH_COOKIE_NAME,
        access,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=_settings.access_token_expires_min * 60,
        path="/",
    )
    response.set_cookie(
        AUTH_REFRESH_COOKIE_NAME,
        refresh,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=_settings.refresh_token_expires_days * 86400,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    is_prod = _settings.app_env == "production"
    for name in (AUTH_COOKIE_NAME, AUTH_REFRESH_COOKIE_NAME):
        response.delete_cookie(
            name,
            path="/",
            secure=is_prod,
            samesite="lax",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_ip("register", limit=5, window_s=3600))],
)
async def register(
    payload: UserCreate, response: Response, db: AsyncSession = Depends(get_db)
):
    # Check uniqueness
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access = create_token(user.id, user.email)
    refresh, _refresh_row = await create_refresh_token(db, user.id)
    await db.commit()

    _set_auth_cookies(response, access=access, refresh=refresh)
    return AuthResponse(user=UserOut.model_validate(user), token=access)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit_ip("login", limit=10, window_s=60))],
)
async def login(
    payload: UserLogin, response: Response, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        # Same body either way — prevents account enumeration.
        # Per ADR-010 §10.5 the message MUST NOT echo which leg failed.
        raise AuthenticationError(detail="Invalid credentials")
    access = create_token(user.id, user.email)
    refresh, _refresh_row = await create_refresh_token(db, user.id)
    await db.commit()

    _set_auth_cookies(response, access=access, refresh=refresh)
    return AuthResponse(user=UserOut.model_validate(user), token=access)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    auth_refresh: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Rotate the refresh-token cookie into a fresh access + refresh pair.

    Returns 401 if the cookie is absent, the row is missing, or the row
    has been revoked. On success the old refresh row is revoked and a
    new one is inserted (rotation, per ADR-015 §15.9 item 3). Both
    cookies are re-set on the response.
    """
    rotated = await rotate_refresh_token(db, auth_refresh or "")
    if rotated is None:
        # No cookie, unknown hash, or already revoked — clear any
        # residual cookies so the client does not loop.
        _clear_auth_cookies(response)
        raise AuthenticationError(detail="Invalid or expired refresh token")

    new_raw, _new_row = rotated
    # The user is the same as the rotated token's owner.
    user_id = _new_row.user_id
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None:
        # Defensive: user row vanished under the FK cascade window.
        _clear_auth_cookies(response)
        raise AuthenticationError(detail="Invalid refresh token")

    access = create_token(user.id, user.email)
    await db.commit()

    _set_auth_cookies(response, access=access, refresh=new_raw)
    return AuthResponse(user=UserOut.model_validate(user), token=access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    auth_refresh: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the refresh row + clear both cookies.

    No-op if the cookie is absent (back-compat for pre-H3 deploys
    whose users never received a refresh row). ADR-015 §15.9 item 3.
    """
    if auth_refresh:
        await revoke_refresh_token(db, auth_refresh)
        await db.commit()
    _clear_auth_cookies(response)
    return


@router.get("/me", response_model=UserOut)
async def me(user_id=Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)