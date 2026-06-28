"""Article model — stores scraped articles + summary + topics + source metadata."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.database import Base


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("user_id", "url", name="uq_articles_user_url"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    headline: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    source_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    publish_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user = relationship("User", back_populates="articles")
    feed_items = relationship("FeedItem", back_populates="article")

    def __repr__(self) -> str:
        return f"<Article id={self.id} headline={self.headline!r}>"