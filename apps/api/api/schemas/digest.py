"""Digest + Notification Pydantic schemas (Task #8, ADR-012).

Manual mirror of ``packages/shared/src/types.ts``. Field names + structure
match the TS types; snake_case throughout. Response models carry
``from_attributes=True`` so ``model_validate(orm_row)`` works the same
way ``ArticleOut`` / ``UserOut`` do (see commit b1bb3b7).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------


class DigestSectionOut(BaseModel):
    """One LLM-clustered section of a digest (mirrors TS ``DigestSection``)."""

    cluster_id: str
    topic: str
    summary: str
    article_ids: list[UUID]
    rank: int


class DigestOut(BaseModel):
    """Public response shape for a fully-generated digest."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    for_date: date
    overall_summary: str
    sections: list[DigestSectionOut] = Field(default_factory=list)
    generated_at: datetime
    delivery_status: Literal["pending", "notified", "emailed", "failed"] = "pending"
    email_message_id: Optional[str] = None


class DigestListResponse(BaseModel):
    """Cursor-paginated digest list (mirrors TS ``DigestListResponse``)."""

    digests: list[DigestOut]
    next_cursor: Optional[str] = None


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


class NotificationOut(BaseModel):
    """Public response shape for an in-app notification."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    kind: Literal["brief_ready", "brief_failed", "system"]
    title: str
    preview: str
    href: Optional[str] = None
    digest_id: Optional[UUID] = None
    read: bool
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    """Simple (non-cursor) list wrapper for the ``/notifications`` endpoint."""

    items: list[NotificationOut]
    total: int


# ---------------------------------------------------------------------------
# Email payload (internal — not exposed via router)
# ---------------------------------------------------------------------------


class EmailDigestPayload(BaseModel):
    """Payload handed from the digest worker to the SMTP transport.

    Mirrors TS ``EmailDigestPayload`` (M2 — the raw email is intentionally
    absent). The SMTP transport looks up the recipient address from the
    ``users`` table using ``recipient_user_id`` right before the send —
    raw PII never crosses the worker→transport boundary, so retry queues
    / log lines / exception tracebacks cannot leak it (ADR-012 §12.7).

    Lives in the schema module so the worker and the digest service
    share one type without crossing into the routers package.
    """

    recipient_user_id: UUID
    digest_id: UUID
    for_date: date
    text_body: str
    html_body: str
    list_unsubscribe_url: str
    list_unsubscribe_header: str


class UnsubscribeResponse(BaseModel):
    """Response body for ``POST /digest/{digest_id}/unsubscribe``.

    Mirrors TS ``UnsubscribeResponse`` (M4). Always 200 OK with a body
    (never 204) so a confirmation page can read the result.
    """

    unsubscribed: bool
    at: datetime
