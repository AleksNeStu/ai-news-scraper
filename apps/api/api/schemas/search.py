"""Search schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError

from api.schemas.article import ArticleOut


class SearchFilters(BaseModel):
    source: Optional[str] = None
    topics: Optional[list[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    @model_validator(mode="after")
    def _date_to_not_before_date_from(self) -> "SearchFilters":
        # ADR-019 §19.5. Fires only when BOTH bounds are set AND
        # date_to < date_from. Single-bound and empty-filter payloads
        # pass through untouched.
        #
        # We raise ``PydanticCustomError`` (not a raw ``ValueError``)
        # because the project's exception handler at ``api.main`` passes
        # ``exc.errors()`` through ``json.dumps`` for the 422 body.
        # A raw ``ValueError`` lands in Pydantic's ``ctx['error']`` and
        # is not JSON-serialisable — the catch-all then returns 500
        # instead of 422. ``PydanticCustomError`` is rendered as a
        # string by Pydantic and survives the JSON round-trip. The
        # client-facing message is the same; the type code is
        # ``value_error`` so it matches the convention used by the rest
        # of the API's 422 responses.
        if self.date_from is not None and self.date_to is not None:
            if self.date_to < self.date_from:
                raise PydanticCustomError(
                    "value_error",
                    "date_to must be greater than or equal to date_from",
                )
        return self


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
                "search: top_k=%s ignored, page_size=%s used",
                self.top_k,
                self.page_size,
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
