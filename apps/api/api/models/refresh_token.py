"""RefreshToken model — server-side logout invalidation.

Per ADR-015 (``.agent/adr/015-auth-hardening.md`` §15.9), H3 stores
opaque refresh tokens as their SHA-256 hash (NEVER the raw token).
Logout sets ``revoked_at = now()``; ``/auth/refresh`` only honours
rows where ``revoked_at IS NULL``. The composite index on
``(user_id, revoked_at)`` supports both the per-user listing and
the equality lookup on a non-revoked row.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index(
            "ix_refresh_tokens_user_id_revoked_at",
            "user_id",
            "revoked_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SHA-256 hex digest of the raw token (64 chars). We never store
    # the raw token — same posture as storing ``hashed_password``,
    # not the plaintext.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user_id={self.user_id}>"
