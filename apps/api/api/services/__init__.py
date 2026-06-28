"""Business logic services — no FastAPI imports here.

This package's submodules have *uneven* import cost: ``auth`` is pure
Python (cheap), while ``scraper`` pulls in ``newspaper3k`` (heavy C
deps). To keep the cheap ones cheap, this ``__init__`` exposes the
symbols via lazy ``__getattr__`` — no top-level imports happen on
``import api.services``.

Code paths that need a specific service should still import it directly:
    from api.services.scraper import ArticleScraper

That keeps the dependency footprint of the importer explicit and matches
what every router already does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api.services.auth import (
        AuthService,
        create_token,
        decode_token,
        hash_password,
        verify_password,
    )
    from api.services.embedder import ArticleEmbedder
    from api.services.feed_parser import FeedParser
    from api.services.scraper import ArticleScraper
    from api.services.summarizer import ArticleSummarizer
    from api.services.vector_store import BaseVectorStore, ChromaVectorStore

__all__ = [
    "ArticleScraper",
    "ArticleSummarizer",
    "ArticleEmbedder",
    "ChromaVectorStore",
    "BaseVectorStore",
    "FeedParser",
    "AuthService",
    "hash_password",
    "verify_password",
    "create_token",
    "decode_token",
]

_LAZY_MAP: dict[str, str] = {
    "ArticleScraper": "api.services.scraper",
    "ArticleSummarizer": "api.services.summarizer",
    "ArticleEmbedder": "api.services.embedder",
    "ChromaVectorStore": "api.services.vector_store",
    "BaseVectorStore": "api.services.vector_store",
    "FeedParser": "api.services.feed_parser",
    "AuthService": "api.services.auth",
    "hash_password": "api.services.auth",
    "verify_password": "api.services.auth",
    "create_token": "api.services.auth",
    "decode_token": "api.services.auth",
}


def __getattr__(name: str) -> Any:
    """Resolve a name on first access by importing its source module."""
    module_path = _LAZY_MAP.get(name)
    if module_path is None:
        raise AttributeError(f"module 'api.services' has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value  # cache for next access
    return value
