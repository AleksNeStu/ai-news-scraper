"""JWT auth service — bcrypt + PyJWT."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

from api.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: UUID, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_settings.jwt_expires_min)).timestamp()),
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid JWT: %s", e)
        return None


class AuthService:
    """Convenience facade — wires the helpers together."""

    @staticmethod
    def register(email: str, password: str) -> tuple[UUID, str]:
        from api.models.user import User  # local to avoid circular imports
        from sqlalchemy import select

        from api.db.database import AsyncSessionLocal

        async def _create() -> tuple[UUID, str]:
            async with AsyncSessionLocal() as session:
                # Check uniqueness
                existing = await session.execute(select(User).where(User.email == email))
                if existing.scalar_one_or_none() is not None:
                    raise ValueError("email already registered")
                user = User(email=email, hashed_password=hash_password(password))
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user.id, create_token(user.id, user.email)

        import asyncio

        return asyncio.get_event_loop().run_until_complete(_create())

    @staticmethod
    def login(email: str, password: str) -> tuple[UUID, str] | None:
        from api.models.user import User
        from sqlalchemy import select

        from api.db.database import AsyncSessionLocal

        async def _check() -> tuple[UUID, str] | None:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(User).where(User.email == email))
                user = res.scalar_one_or_none()
                if user is None or not verify_password(password, user.hashed_password):
                    return None
                return user.id, create_token(user.id, user.email)

        import asyncio

        return asyncio.get_event_loop().run_until_complete(_check())