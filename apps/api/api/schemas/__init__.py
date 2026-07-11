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
from api.schemas.feed import (
    FeedOut,
    FeedCreate,
    FeedListResponse,
    FeedItemOut,
    OpmlFeedRef,
    BulkImportRequest,
    BulkImportFailure,
    BulkImportResult,
)
from api.schemas.auth import UserCreate, UserLogin, UserOut, AuthResponse
from api.schemas.share import (
    ShareCreateRequest,
    ShareResponse,
    SharedArticleView,
)
from api.schemas.embeddings import (
    EmbeddingProvider,
    EmbeddingProvidersResponse,
    EmbedRequest,
    EmbedResponse,
    SimilarityRequest,
    SimilarityResponse,
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
    "OpmlFeedRef",
    "BulkImportRequest",
    "BulkImportFailure",
    "BulkImportResult",
    "UserCreate",
    "UserLogin",
    "UserOut",
    "AuthResponse",
    "ShareCreateRequest",
    "ShareResponse",
    "SharedArticleView",
    "EmbeddingProvider",
    "EmbeddingProvidersResponse",
    "EmbedRequest",
    "EmbedResponse",
    "SimilarityRequest",
    "SimilarityResponse",
]
