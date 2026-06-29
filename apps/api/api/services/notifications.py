"""Notification service — list + mark-read for the in-app inbox
(Task #8, ADR-012 §12.2).

The DB row is the source of truth; this module is a thin async
query/mutation layer. Tenant isolation lives here: every query is
scoped to ``user_id`` so a leaked UUID cannot pull another user's
rows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.exceptions import NotFoundError
from api.models.digest import Notification

logger = logging.getLogger(__name__)


async def list_notifications(
    session: AsyncSession,
    user_id: UUID,
    *,
    unread_only: bool = False,
    limit: int = 50,
    cursor: datetime | None = None,
) -> list[Notification]:
    """List the user's notifications newest-first.

    Pagination is cursor-based on ``created_at`` (older-than-or-equal
    to ``cursor``) — matches the brief's ``?cursor=...`` shape without
    exposing opaque tokens in v1.
    """
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    if cursor is not None:
        stmt = stmt.where(Notification.created_at < cursor)
    stmt = stmt.order_by(Notification.created_at.desc()).limit(max(1, min(limit, 200)))

    res = await session.execute(stmt)
    return list(res.scalars().all())


async def count_notifications(
    session: AsyncSession,
    user_id: UUID,
    *,
    unread_only: bool = False,
) -> int:
    """Total count for the user's inbox (used by the router response)."""
    stmt = select(func.count(Notification.id)).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    res = await session.execute(stmt)
    return int(res.scalar_one() or 0)


async def mark_read(
    session: AsyncSession, user_id: UUID, notification_id: UUID
) -> Notification:
    """Mark one notification read; raises ``NotFoundError`` if it isn't
    the user's (or doesn't exist).

    Multi-tenant safety: the WHERE includes ``user_id``; rows belonging
    to other users simply do not match and we raise 404 — never 403,
    per ADR-012 §12.7 (don't leak existence across tenants).
    """
    res = await session.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise NotFoundError("Notification not found")
    if not row.read:
        row.read = True
        row.read_at = datetime.now(timezone.utc)
        await session.flush()
    return row
