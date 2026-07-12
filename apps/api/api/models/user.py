"""User model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.database import Base


class User(Base):
    __tablename__ = "users"
    # Task #31 / Devil M2 — declare the email uniqueness explicitly in
    # __table_args__ so the autogenerate name matches the migration's
    # ``uq_users_email`` (instead of the Postgres-default
    # ``users_email_key`` that ``unique=True`` on a column would emit).
    # The original migration (1890892bda24) used a hand-written named
    # UniqueConstraint; the prior model used the column-level
    # ``unique=True, index=True`` markers, which SQLAlchemy resolved
    # to a different name — masking autogenerate drift. Naming is now
    # pinned at both layers.
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # RFC 8058 one-click unsubscribe target — flipped to ``False`` when
    # the user hits the unsubscribe link (see services/unsubscribe.py).
    email_digest_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )

    articles = relationship(
        "Article", back_populates="user", cascade="all, delete-orphan"
    )
    feeds = relationship("Feed", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
