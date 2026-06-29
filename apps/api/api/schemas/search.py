"""Search schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from api.schemas.article import ArticleOut


class SearchFilters(BaseModel):
    source: Optional[str] = None
    topics: Optional[list[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: Optional[SearchFilters] = None


class SearchResult(BaseModel):
    article: ArticleOut
    score: float
    highlights: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    results: list[SearchResult]
    took_ms: int
