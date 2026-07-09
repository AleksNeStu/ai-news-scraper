"""SQLAlchemy models for public shareable article links.

Task #33 / ADR-021. Two tables that together implement the
``POST /share`` + ``GET /s/{token}`` surface.

* ``SharedLink`` — the mint record. ``token_hash`` is the SHA-256 hex
  digest of the raw ``secrets.token_urlsafe(32)`` token; the raw token
  is never persisted (only returned in the ``POST /share`` response
  body and the URL the user pastes). The unique index on
  ``token_hash`` is the lookup key for ``GET /s/{token}``.
* ``SharedLinkVisit`` — append-only audit row for unauthenticated
  reads. The ``(shared_link_id, visited_at_bucket)`` UNIQUE constraint
  is the per-second de-dupe key that makes concurrent GETs race-free
  (ADR-021 §21.6). ``shared_links.visits`` is a cached roll-up that a
  background job refreshes from this table — it is NOT incremented on
  the request path.

Cascade posture: deleting an article wipes every share of that
article in one statement (GDPR-style retraction). Account deletion
cascades transitively via ``articles.user_id``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.database import Base


class SharedLink(Base):
    """One row per public shareable URL minted via ``POST /share``."""

    __tablename__ = "shared_links"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_shared_links_token_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 hex digest of the raw token (64 chars). The raw token is
    # only held in the POST response body and the URL — it is NEVER
    # persisted (ADR-021 §21.1).
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # Cached roll-up of ``shared_link_visits`` rows. Refreshed by a
    # background job; NOT written on the request path (ADR-021 §21.6).
    visits: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    article = relationship("Article")
    visits_log = relationship(
        "SharedLinkVisit",
        back_populates="shared_link",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<SharedLink id={self.id} article_id={self.article_id} "
            f"expires_at={self.expires_at!r}>"
        )


class SharedLinkVisit(Base):
    """One row per de-duped (per-second) visit to a public share URL."""

    __tablename__ = "shared_link_visits"
    __table_args__ = (
        # The bucket-unique constraint is the de-dupe key for concurrent
        # GETs (ADR-021 §21.6). Two visits in the same second collapse
        # to one row, then ``ON CONFLICT DO NOTHING`` makes the insert
        # idempotent under replay.
        UniqueConstraint(
            "shared_link_id",
            "visited_at_bucket",
            name="uq_shared_link_visits_link_bucket",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    shared_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shared_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Per-second bucket — coarse enough that simultaneous GETs from the
    # same visitor collapse, fine enough that real visit frequency is
    # preserved (ADR-021 §21.6).
    visited_at_bucket: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    shared_link = relationship("SharedLink", back_populates="visits_log")

    def __repr__(self) -> str:
        return (
            f"<SharedLinkVisit id={self.id} shared_link_id="
            f"{self.shared_link_id} bucket={self.visited_at_bucket!r}>"
        )