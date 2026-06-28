"""Feed / RSS schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class FeedCreate(BaseModel):
    feed_url: HttpUrl


class FeedOut(BaseModel):
    id: UUID
    feed_url: str
    title: Optional[str] = None
    description: Optional[str] = None
    last_polled: Optional[datetime] = None
    active: bool
    item_count: int = 0
    created_at: datetime


class FeedListResponse(BaseModel):
    items: list[FeedOut]
    total: int


class FeedItemOut(BaseModel):
    id: UUID
    feed_id: UUID
    article_id: Optional[UUID] = None
    guid: str
    title: Optional[str] = None
    url: Optional[str] = None
    fetched_at: datetime