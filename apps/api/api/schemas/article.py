"""Article / scrape schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ArticleOut(BaseModel):
    id: UUID
    url: str
    headline: Optional[str] = None
    body: Optional[str] = None
    summary: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    source_domain: Optional[str] = None
    publish_date: Optional[datetime] = None
    indexed_at: datetime


class ArticleListResponse(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


class ScrapeRequest(BaseModel):
    url: HttpUrl


class BatchScrapeRequest(BaseModel):
    urls: list[HttpUrl] = Field(..., max_length=50)