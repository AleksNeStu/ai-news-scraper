"""Digest router — read-only views over the user's daily briefs +
RFC 8058 unsubscribe (Task #8, ADR-012 §12.2).

Routes:
    GET  /digest/today                       Today's digest (404 if not generated).
    GET  /digest/{for_date}                  Digest for a specific UTC date.
    GET  /digest                             Cursor-paginated history.
    POST /digest/{digest_id}/unsubscribe     RFC 8058 §3.2 one-click. Token-only auth.

Generation is owned by the scheduler + ``services.digest.generate_digest``.
This router only reads; it does NOT trigger generation (a 404 on missing
is the honest answer — the Web UX can hit a separate "regenerate now"
endpoint if needed, out of v1 scope per ADR-012 §12.2).
"""

from __future__ import annotations

import json
from datetime import date as _date
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.deps import get_current_user_id
from api.models.digest import Digest
from api.schemas.digest import (
    DigestListResponse,
    DigestOut,
    DigestSectionOut,
    UnsubscribeResponse,
)
from api.services.unsubscribe import consume_unsubscribe

router = APIRouter(prefix="/digest", tags=["digest"])


# ---------------------------------------------------------------------------
# Serialisation helper — DB row → DigestOut
# ---------------------------------------------------------------------------


def _to_digest_out(row: Digest) -> DigestOut:
    """Hydrate the ORM row into a ``DigestOut``.

    ``sections_json`` is ``dict`` (JSONB column); convert to the typed
    ``DigestSectionOut`` list here so the router contract stays tight.
    """
    raw_sections = row.sections_json or {}
    if isinstance(raw_sections, str):
        # Defensive: some PG drivers hand back JSON-as-string.
        raw_sections = json.loads(raw_sections)
    sections_payload = (
        raw_sections.get("sections") if isinstance(raw_sections, dict) else None
    )
    if sections_payload is None and isinstance(raw_sections, list):
        sections_payload = raw_sections
    sections_payload = sections_payload or []
    sections = [DigestSectionOut.model_validate(s) for s in sections_payload]
    return DigestOut(
        id=row.id,
        user_id=row.user_id,
        for_date=row.for_date,
        overall_summary=row.overall_summary,
        sections=sections,
        generated_at=row.generated_at,
        delivery_status=row.delivery_status,
        email_message_id=row.email_message_id,
    )


def _parse_date(raw: str) -> _date:
    """Parse a ``YYYY-MM-DD`` date string for the path param."""
    try:
        return _date.fromisoformat(raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="for_date must be YYYY-MM-DD",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/today", response_model=DigestOut)
async def get_today_digest(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DigestOut:
    """Return today's digest (UTC date) for the caller, or 404."""
    today = datetime.now(timezone.utc).date()
    res = await db.execute(
        select(Digest).where(
            Digest.user_id == user_id,
            Digest.for_date == today,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Digest for today not yet generated",
        )
    return _to_digest_out(row)


@router.get("", response_model=DigestListResponse)
async def list_digests(
    cursor: datetime | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DigestListResponse:
    """List the user's digests newest-first with cursor pagination."""
    stmt = select(Digest).where(Digest.user_id == user_id)
    if cursor is not None:
        stmt = stmt.where(Digest.for_date < cursor.date())
    stmt = stmt.order_by(Digest.for_date.desc()).limit(limit + 1)
    res = await db.execute(stmt)
    rows = list(res.scalars().all())
    next_cursor: str | None = None
    if len(rows) > limit:
        next_row = rows[limit]
        next_cursor = next_row.for_date.isoformat()
        rows = rows[:limit]
    return DigestListResponse(
        digests=[_to_digest_out(r) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/{for_date}", response_model=DigestOut)
async def get_digest_by_date(
    for_date: _date,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DigestOut:
    """Return the digest for a specific UTC date, or 404."""
    res = await db.execute(
        select(Digest).where(
            Digest.user_id == user_id,
            Digest.for_date == for_date,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Digest not found for date",
        )
    return _to_digest_out(row)


@router.post("/{digest_id}/unsubscribe", response_model=UnsubscribeResponse)
async def unsubscribe_endpoint(
    digest_id: UUID,
    token: str = Form(...),  # application/x-www-form-urlencoded (RFC 8058 §3.2)
    db: AsyncSession = Depends(get_db),
) -> UnsubscribeResponse:
    """RFC 8058 §3.2 one-click unsubscribe.

    The signed JWT IS the credential — no cookie, no ``Authorization``
    header. Idempotent: a replay returns ``unsubscribed: false`` with
    the original ``consumed_at``. Always 200 OK with a body (never 204).
    """
    return await consume_unsubscribe(db, token)
