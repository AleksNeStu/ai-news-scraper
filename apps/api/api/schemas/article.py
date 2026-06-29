"""Article / scrape schemas."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# Tier literal — mirrored from packages/shared/src/types.ts (ADR-013 §13.4).
# Used by both the response schema and the router query-param parser.
TierLiteral = Literal["must_read", "recommended", "worth_a_look", "low_priority"]


class ArticleOut(BaseModel):
    # Allow ``model_validate(article)`` where ``article`` is a SQLAlchemy
    # ORM instance — Pydantic v2 needs this to read attributes rather than
    # dict keys. Pre-existing bug surfaced during Task #34 acceptance;
    # without this, /scrape, /search, and /articles all raise ValidationError
    # at the response_model step.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    headline: Optional[str] = None
    body: Optional[str] = None
    summary: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    source_domain: Optional[str] = None
    publish_date: Optional[datetime] = None
    indexed_at: datetime
    # Task #9 / ADR-013 §13.4 — tiered curation. All three fields are
    # NULL until the first successful ``score_article`` call; the
    # front-end ScoreRing renders an empty ring when ``score`` is null
    # (ADR-013 §13.3 — never a 0.0 ring that lies).
    score: Optional[float] = None
    tier: Optional[TierLiteral] = None
    scored_at: Optional[datetime] = None


class ArticleListResponse(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


class ScrapeRequest(BaseModel):
    url: HttpUrl


class BatchScrapeRequest(BaseModel):
    urls: list[HttpUrl] = Field(..., max_length=50)
