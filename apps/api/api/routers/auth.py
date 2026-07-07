"""Auth router — register, login, logout, me.

H2: ``/auth/login`` is now gated by ``rate_limit_ip("login", ...)``
at 10 hits / 60s / IP per ADR-015 §15.8. ``/auth/register`` keeps
its existing 5/3600 limit. H1 lives in ``schemas/auth.py``.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.db.database import get_db
from api.deps import AUTH_COOKIE_NAME, get_current_user_id
from api.middleware.rate_limit import rate_limit_ip
from api.models.user import User
from api.schemas.auth import AuthResponse, UserCreate, UserLogin, UserOut
from api.services.auth import create_token

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


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
        hashed_password=__import__(
            "api.services.auth", fromlist=["hash_password"]
        ).hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_token(user.id, user.email)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_settings.app_env == "production",
        samesite="lax",
        max_age=_settings.jwt_expires_min * 60,
        path="/",
    )
    return AuthResponse(user=UserOut.model_validate(user), token=token)


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
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not __import__(
        "api.services.auth", fromlist=["verify_password"]
    ).verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user.id, user.email)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_settings.app_env == "production",
        samesite="lax",
        max_age=_settings.jwt_expires_min * 60,
        path="/",
    )
    return AuthResponse(user=UserOut.model_validate(user), token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return


@router.get("/me", response_model=UserOut)
async def me(user_id=Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)
