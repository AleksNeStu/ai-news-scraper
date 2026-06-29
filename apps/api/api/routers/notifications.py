"""Notifications router — in-app inbox (Task #8, ADR-012 §12.2).

Routes:
    GET  /notifications?unread_only=true&limit=50&cursor=...
    POST /notifications/{id}/read

Tenant isolation: every query is scoped to the caller's ``user_id``.
A foreign UUID returns 404 (not 403) per ADR-012 §12.7 — never leak
existence across tenants.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.deps import get_current_user_id
from api.schemas.digest import NotificationListResponse, NotificationOut
from api.services.notifications import (
    count_notifications,
    list_notifications,
    mark_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_user_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: datetime | None = Query(default=None),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """List the caller's notifications, newest-first."""
    items = await list_notifications(
        db,
        user_id,
        unread_only=unread_only,
        limit=limit,
        cursor=cursor,
    )
    total = await count_notifications(db, user_id, unread_only=unread_only)
    return NotificationListResponse(
        items=[NotificationOut.model_validate(i) for i in items],
        total=total,
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    """Mark one notification read; 404 if it isn't the caller's."""
    row = await mark_read(db, user_id, notification_id)
    await db.commit()
    await db.refresh(row)
    return NotificationOut.model_validate(row)
