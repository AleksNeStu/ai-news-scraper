"""RFC 8058 one-click unsubscribe service (Task #8, ADR-012 §12.7).

Two entry points:

* ``mint_unsubscribe_token(digest_id, user_id)`` — produces a JWT the
  SMTP worker embeds in the ``List-Unsubscribe`` headers + HTML body.
  Carries ``kid`` (digest-local) + ``jti`` (unique per token) so the
  verifier can detect replay against ``digest_unsubscribe_log``.

* ``consume_unsubscribe(session, token)`` — verifies the token, refuses
  expired/invalid/foreign tokens, and on first consumption INSERTs
  into ``digest_unsubscribe_log`` (UNIQUE(jwt_id) is the DB-level
  replay guard), then flips ``users.email_digest_enabled = False``.
  On replay returns ``UnsubscribeResponse(unsubscribed=False, at=<orig>)``.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.exceptions import ValidationError
from api.models.digest import DigestUnsubscribeLog
from api.models.user import User
from api.schemas.digest import UnsubscribeResponse

logger = logging.getLogger(__name__)


def mint_unsubscribe_token(digest_id: UUID, user_id: UUID, ttl_days: int = 30) -> str:
    """Produce a one-click unsubscribe JWT.

    ``kid`` header = ``digest_id`` (digest-local key id); ``jti`` claim
    = unique per token, used for replay protection at the DB layer.
    """
    s = get_settings()
    if not s.unsubscribe_jwt_secret:
        raise RuntimeError(
            "UNSUBSCRIBE_JWT_SECRET not configured; cannot mint unsubscribe tokens"
        )
    jti = uuid.uuid4().hex
    now = int(time.time())
    payload = {
        "digest_id": str(digest_id),
        "user_id": str(user_id),
        "action": "unsubscribe",
        "jti": jti,
        "iat": now,
        "exp": now + ttl_days * 86400,
    }
    return jwt.encode(
        payload,
        s.unsubscribe_jwt_secret,
        algorithm="HS256",
        headers={"kid": str(digest_id)},
    )


async def consume_unsubscribe(session: AsyncSession, token: str) -> UnsubscribeResponse:
    """Verify + consume an unsubscribe token.

    Behaviour:
      * expired/invalid/foreign-action token → ``ValidationError`` (400).
      * first-time ``jti`` → INSERT into ``digest_unsubscribe_log``,
        flip ``users.email_digest_enabled=False``, return
        ``unsubscribed=True`` + current UTC time.
      * replay (jti already in log) → return ``unsubscribed=False`` +
        original ``consumed_at`` (idempotent per RFC 8058 §3.2).
    """
    s = get_settings()
    try:
        payload = jwt.decode(token, s.unsubscribe_jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise ValidationError(f"unsubscribe token expired: {e}")
    except jwt.InvalidTokenError as e:
        raise ValidationError(f"invalid unsubscribe token: {e}")

    if payload.get("action") != "unsubscribe":
        raise ValidationError("token action is not unsubscribe")

    jti = payload["jti"]
    digest_id = UUID(payload["digest_id"])
    user_id = UUID(payload["user_id"])

    # Replay check.
    existing = await session.scalar(
        select(DigestUnsubscribeLog).where(DigestUnsubscribeLog.jwt_id == jti)
    )
    if existing is not None:
        original_at = existing.consumed_at
        if original_at.tzinfo is None:
            original_at = original_at.replace(tzinfo=timezone.utc)
        logger.info(
            "unsubscribe: replay (already consumed)",
            extra={"digest_id": str(digest_id), "user_id": str(user_id)},
        )
        return UnsubscribeResponse(unsubscribed=False, at=original_at)

    # First-time consumption: insert log row (UNIQUE(jwt_id) guards at DB level),
    # then flip the user's email preference.
    now = datetime.now(timezone.utc)
    log_row = DigestUnsubscribeLog(
        digest_id=digest_id,
        user_id=user_id,
        jwt_id=jti,
        consumed_at=now,
    )
    session.add(log_row)
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is not None:
        user.email_digest_enabled = False
    await session.commit()
    return UnsubscribeResponse(unsubscribed=True, at=now)


__all__ = ["mint_unsubscribe_token", "consume_unsubscribe"]
