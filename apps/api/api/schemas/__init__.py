"""Pydantic request/response schemas."""

from api.schemas.article import (
    ArticleOut,
    ArticleListResponse,
    ScrapeRequest,
    BatchScrapeRequest,
)
from api.schemas.search import (
    SearchRequest,
    SearchResult,
    SearchResponse,
    SearchFilters,
)
from api.schemas.feed import FeedOut, FeedCreate, FeedListResponse, FeedItemOut
from api.schemas.auth import UserCreate, UserLogin, UserOut, AuthResponse
from api.schemas.share import (
    ShareCreateRequest,
    ShareResponse,
    SharedArticleView,
)

__all__ = [
    "ArticleOut",
    "ArticleListResponse",
    "ScrapeRequest",
    "BatchScrapeRequest",
    "SearchRequest",
    "SearchResult",
    "SearchResponse",
    "SearchFilters",
    "FeedOut",
    "FeedCreate",
    "FeedListResponse",
    "FeedItemOut",
    "UserCreate",
    "UserLogin",
    "UserOut",
    "AuthResponse",
    "ShareCreateRequest",
    "ShareResponse",
    "SharedArticleView",
]
