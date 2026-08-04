"""Pydantic request/response schemas."""

from api.schemas.article import (
    ArticleListResponse,
    ArticleOut,
    BatchScrapeRequest,
    ScrapeRequest,
)
from api.schemas.auth import AuthResponse, UserCreate, UserLogin, UserOut
from api.schemas.embeddings import (
    EmbeddingProvider,
    EmbeddingProvidersResponse,
    EmbedRequest,
    EmbedResponse,
    SimilarityRequest,
    SimilarityResponse,
)
from api.schemas.feed import (
    BulkImportFailure,
    BulkImportRequest,
    BulkImportResult,
    FeedCreate,
    FeedItemOut,
    FeedListResponse,
    FeedOut,
    OpmlFeedRef,
)
from api.schemas.search import (
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from api.schemas.share import (
    ShareCreateRequest,
    SharedArticleView,
    ShareResponse,
)

__all__ = [
    "ArticleListResponse",
    "ArticleOut",
    "AuthResponse",
    "BatchScrapeRequest",
    "BulkImportFailure",
    "BulkImportRequest",
    "BulkImportResult",
    "EmbedRequest",
    "EmbedResponse",
    "EmbeddingProvider",
    "EmbeddingProvidersResponse",
    "FeedCreate",
    "FeedItemOut",
    "FeedListResponse",
    "FeedOut",
    "OpmlFeedRef",
    "ScrapeRequest",
    "SearchFilters",
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    "ShareCreateRequest",
    "ShareResponse",
    "SharedArticleView",
    "SimilarityRequest",
    "SimilarityResponse",
    "UserCreate",
    "UserLogin",
    "UserOut",
]
