"""Digest + Notification models — AI Brief (Task #8, ADR-012).

A ``Digest`` row holds one full per-user daily brief: the LLM-clustered
sections + the overall summary + delivery state. ``Notification`` is
the in-app surface that points the user at a fresh digest (or a
system/brief_failed event).

Pydantic mirrors live in ``apps/api/api/schemas/digest.py`` and TS types
in ``packages/shared/src/types.ts`` (manual sync).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db.database import Base

# The terminal / non-terminal states of ``Digest.delivery_status``.
# Mirrors the TS ``DigestStatus`` union (``packages/shared/src/types.ts``)
# AND the Pydantic ``Literal`` in ``api/schemas/digest.py``.
DigestStatus = Literal["pending", "notified", "emailed", "failed"]

__all__ = ["Digest", "DigestStatus", "DigestUnsubscribeLog", "Notification"]


class Digest(Base):
    __tablename__ = "digests"
    __table_args__ = (
        UniqueConstraint("user_id", "for_date", name="uq_digests_user_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    for_date: Mapped[datetime] = mapped_column(Date, index=True, nullable=False)
    overall_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sections_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    delivery_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    email_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Digest id={self.id} user_id={self.user_id} "
            f"for_date={self.for_date} status={self.delivery_status!r}>"
        )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    preview: Mapped[str] = mapped_column(String(280), nullable=False)
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)
    digest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("digests.id", ondelete="SET NULL"),
        nullable=True,
    )
    read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} user_id={self.user_id} "
            f"kind={self.kind!r} read={self.read}>"
        )


class DigestUnsubscribeLog(Base):
    """RFC 8058 §3.2 one-click unsubscribe replay log.

    One row per consumed JWT. The DB-level ``UNIQUE(jwt_id)`` constraint
    is the authoritative replay guard — application-level check-then-INSERT
    is racy; the constraint catches concurrent races on the same jti.
    """

    __tablename__ = "digest_unsubscribe_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    digest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("digests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    jwt_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<DigestUnsubscribeLog id={self.id} digest_id={self.digest_id} "
            f"user_id={self.user_id} jwt_id={self.jwt_id[:8]}...>"
        )
