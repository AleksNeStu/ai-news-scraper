"""JWT auth service — bcrypt + PyJWT + refresh-token persistence."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import bcrypt
import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)
_settings = get_settings()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError, bcrypt.exceptions.BcryptError):
        return False


def create_token(user_id: UUID, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=_settings.access_token_expires_min)).timestamp()
        ),
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid JWT: %s", e)
        return None


# ---------------------------------------------------------------------------
# Refresh-token helpers — ADR-015 §15.9.
#
# The raw token is ``secrets.token_hex(32)`` (256 bits of entropy).
# We store ONLY ``sha256(raw_token).hexdigest()`` — same posture as
# ``hashed_password``: a DB leak must not yield usable tokens. The
# helper trio below is the single call site for refresh lifecycle.
# ---------------------------------------------------------------------------


def _hash_refresh_token(raw_token: str) -> str:
    """SHA-256 hex digest of the raw refresh token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    """Mint a new opaque 256-bit refresh token (raw hex).

    Distinct from ``create_token`` (which mints a JWT) — refresh
    tokens are NOT JWTs. They are random opaque blobs whose only
    security property is their unguessable entropy.
    """
    return secrets.token_hex(32)


async def create_refresh_token(
    db: AsyncSession, user_id: UUID
) -> tuple[str, RefreshToken]:
    """Create a refresh-token row and return ``(raw_token, row)``.

    The caller stores ``row`` (the DB-side representation) and returns
    ``raw_token`` to the user via the ``auth_refresh`` HttpOnly cookie.
    The raw token never lives in the DB.
    """
    raw = generate_refresh_token()
    row = RefreshToken(
        id=uuid4(),
        user_id=user_id,
        token_hash=_hash_refresh_token(raw),
    )
    db.add(row)
    await db.flush()
    return raw, row


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> bool:
    """Revoke the row whose hash matches ``raw_token``.

    Returns ``True`` iff a non-revoked row was found and updated.
    A no-op for unknown / already-revoked tokens — the logout path
    tolerates either case (the cookie is gone after the response).
    """
    if not raw_token:
        return False
    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == _hash_refresh_token(raw_token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
        .returning(RefreshToken.id)
    )
    return result.scalar_one_or_none() is not None


async def lookup_active_refresh_token(
    db: AsyncSession, raw_token: str
) -> RefreshToken | None:
    """Return the active row for ``raw_token`` or ``None`` if missing / revoked."""
    if not raw_token:
        return None
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == _hash_refresh_token(raw_token),
            RefreshToken.revoked_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def rotate_refresh_token(
    db: AsyncSession, raw_token: str
) -> tuple[str, RefreshToken] | None:
    """Atomically revoke ``raw_token`` and mint a new one.

    Returns ``(new_raw_token, new_row)`` on success; ``None`` if the
    incoming token was unknown, already revoked, or absent. The
    caller is responsible for setting both cookies on success.
    """
    existing = await lookup_active_refresh_token(db, raw_token)
    if existing is None:
        return None
    existing.revoked_at = datetime.now(timezone.utc)
    await db.flush()
    return await create_refresh_token(db, existing.user_id)
