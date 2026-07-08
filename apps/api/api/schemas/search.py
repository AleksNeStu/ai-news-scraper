"""Search schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from api.schemas.article import ArticleOut


class SearchFilters(BaseModel):
    source: Optional[str] = None
    topics: Optional[list[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class SearchRequest(BaseModel):
    """Search payload.

    Pagination contract (Task #47):
      - `page` is 1-indexed, `page_size` defaults to 10, max 100.
      - `top_k` is retained as a deprecated synonym for `page_size`
        so existing callers don't break on deploy. The router resolves
        the effective page_size as `(page_size if explicitly set
        else top_k if explicitly set else 10)`.
    """

    query: str = Field(..., min_length=1, max_length=2000)
    top_k: Optional[int] = Field(default=None, ge=1, le=100)
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=10, ge=1, le=100)
    filters: Optional[SearchFilters] = None

    @model_validator(mode="after")
    def _no_both_top_k_and_page_size(self) -> "SearchRequest":
        if self.top_k is not None and self.page_size != 10:
            # Caller set both — prefer the explicit page_size, warn in log.
            import logging

            logging.getLogger(__name__).info(
                "search: top_k=%s ignored, page_size=%s used", self.top_k, self.page_size
            )
        return self


class SearchResult(BaseModel):
    article: ArticleOut
    score: float
    highlights: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    results: list[SearchResult]
    took_ms: int
    page: int
    page_size: int
    total: int
