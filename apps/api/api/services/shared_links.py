"""Service layer for public shareable article links.

Task #33 / ADR-021. Three entry points owned by this module:

* :func:`mint_share` — generate a new token + persist the mint record.
* :func:`resolve_share` — look up a token hash and surface a typed
  ``ShareNotFound`` / ``ShareExpired`` for the router to convert.
* :func:`record_visit` — idempotent audit insert + count (ADR-021
  §21.6). The ``(shared_link_id, visited_at_bucket)`` UNIQUE
  constraint is the per-second de-dupe key that keeps concurrent GETs
  race-free; the live count is a single index scan.

The service is intentionally thin on HTTP concerns — the routers call
these directly and own the response-shape decisions. The audit-row
insert and count are wrapped in a single transaction so the count
cannot drift from the row state.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.exceptions import NotFoundError
from api.models.article import Article
from api.models.shared_link import SharedLink, SharedLinkVisit

logger = logging.getLogger(__name__)


# --- Errors ------------------------------------------------------------------


class ShareError(Exception):
    """Base for share-lookup failures. Subclasses carry their own status."""


class ShareNotFound(ShareError):
    """The token hash did not match any row in ``shared_links``."""


class ShareExpired(ShareError):
    """The token matched a row whose ``expires_at`` is in the past."""

    def __init__(self, token: str, *, expires_at: datetime | None = None) -> None:
        super().__init__(token)
        self.expires_at = expires_at


# --- Token + mint helpers ----------------------------------------------------


def _hash_token(token: str) -> str:
    """SHA-256 hex digest of the raw token (ADR-021 §21.1, §21.9)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _make_token() -> str:
    """``secrets.token_urlsafe(32)`` — 43 chars, ~258 bits of entropy."""
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class MintedShare:
    """Return value of :func:`mint_share` — token + persistence side-effects."""

    token: str
    expires_at: datetime
    shared_link_id: UUID


async def mint_share(
    session: AsyncSession,
    *,
    user_id: UUID,
    article_id: UUID,
    ttl_days: int,
) -> MintedShare:
    """Mint a new share token bound to ``(user_id, article_id, ttl_days)``.

    Verifies the article exists (raises :class:`NotFoundError` otherwise),
    generates a fresh ``secrets.token_urlsafe(32)`` token, persists
    only the SHA-256 hash, and commits the row. The raw token is
    returned to the caller exactly once.
    """
    # Verify the article exists; the FK will catch this too, but an
    # explicit check lets us raise the project's NotFoundError (which
    # the global handler maps to a 404 problem+json) instead of a 500
    # from the FK violation.
    article = await session.scalar(select(Article).where(Article.id == article_id))
    if article is None:
        raise NotFoundError(detail="Article not found")

    token = _make_token()
    token_hash = _hash_token(token)
    # Use ``datetime.now(timezone.utc)`` so the stored value is
    # timezone-aware; comparing naive vs aware datetimes in the
    # ``resolve_share`` path would raise ``TypeError`` in Postgres.
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

    row = SharedLink(
        article_id=article_id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_by=user_id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    return MintedShare(
        token=token,
        expires_at=expires_at,
        shared_link_id=row.id,
    )


# --- Resolve ----------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedShare:
    """Successful result of :func:`resolve_share`."""

    article: Article
    shared_link_id: UUID
    shared_at: datetime
    expires_at: datetime


async def resolve_share(
    session: AsyncSession,
    token: str,
) -> ResolvedShare:
    """Look up a token and return the underlying article.

    Raises :class:`ShareNotFound` when no row matches the SHA-256 hash,
    or :class:`ShareExpired` when the row exists but ``expires_at`` is
    in the past. Both errors map to 404/410 at the router layer
    (ADR-021 §21.7).
    """
    token_hash = _hash_token(token)
    row = await session.scalar(
        select(SharedLink).where(SharedLink.token_hash == token_hash)
    )
    if row is None:
        raise ShareNotFound(token)

    # Compare in UTC. ``row.expires_at`` is timezone-aware (TIMESTAMPTZ),
    # so a naive ``datetime.utcnow()`` would raise ``TypeError``.
    now = datetime.now(timezone.utc)
    if row.expires_at <= now:
        raise ShareExpired(token, expires_at=row.expires_at)

    article = await session.scalar(select(Article).where(Article.id == row.article_id))
    # The article must exist because the FK is ON DELETE CASCADE. If
    # somehow we got here without one (e.g. a DB-level inconsistency
    # during a migration), surface a NotFoundError so the global
    # handler returns 404.
    if article is None:
        raise ShareNotFound(token)

    return ResolvedShare(
        article=article,
        shared_link_id=row.id,
        shared_at=row.created_at,
        expires_at=row.expires_at,
    )


# --- Visit audit ------------------------------------------------------------


async def record_visit(session: AsyncSession, shared_link_id: UUID) -> int:
    """Idempotent audit-row insert + count (ADR-021 §21.6).

    The insert uses ``ON CONFLICT DO NOTHING`` against the
    ``(shared_link_id, visited_at_bucket)`` UNIQUE constraint, so
    concurrent visits from the same visitor in the same second
    collapse to one row. The count is a single index scan.

    Returns the current visit count for the link.
    """
    # Per-second bucket — coarse enough to de-dupe rapid refreshes,
    # fine enough that real visit frequency is preserved (ADR-021 §21.6).
    bucket = datetime.now(timezone.utc).replace(microsecond=0)

    # Single-tx pattern: insert with conflict-do-nothing, then count.
    # No SELECT FOR UPDATE — the audit insert is itself the lock.
    await session.execute(
        text(
            "INSERT INTO shared_link_visits "
            "(shared_link_id, visited_at, visited_at_bucket) "
            "VALUES (:shared_link_id, :visited_at, :bucket) "
            "ON CONFLICT (shared_link_id, visited_at_bucket) DO NOTHING"
        ),
        {
            "shared_link_id": str(shared_link_id),
            "visited_at": datetime.now(timezone.utc),
            "bucket": bucket,
        },
    )
    count = await session.scalar(
        select(func.count(SharedLinkVisit.id)).where(
            SharedLinkVisit.shared_link_id == shared_link_id
        )
    )
    await session.commit()
    return int(count or 0)


__all__ = [
    "MintedShare",
    "ResolvedShare",
    "ShareError",
    "ShareExpired",
    "ShareNotFound",
    "mint_share",
    "record_visit",
    "resolve_share",
]
