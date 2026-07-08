"""Search router — semantic + hybrid search with pagination."""

import logging
import time
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.deps import get_current_user_id
from api.models.article import Article
from api.schemas.article import ArticleOut
from api.schemas.search import SearchRequest, SearchResponse, SearchResult
from api.services.embedder import ArticleEmbedder
from api.services.vector_store import ChromaVectorStore
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])

_embedder = ArticleEmbedder()
_vector_store = ChromaVectorStore()


def _resolve_page_size(payload: SearchRequest) -> int:
    """Effective page_size, honouring the deprecated `top_k` synonym."""
    if payload.top_k is not None:
        return payload.top_k
    return payload.page_size


@router.post("", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    start = time.time()
    page = payload.page
    page_size = _resolve_page_size(payload)
    qvec = await _embedder.embed(payload.query)
    if qvec is None:
        return SearchResponse(
            results=[], took_ms=int((time.time() - start) * 1000),
            page=page, page_size=page_size, total=0,
        )

    where: dict = {"user_id": str(user_id)}
    if payload.filters and payload.filters.source:
        where["source_domain"] = payload.filters.source

    # Over-fetch by `page * page_size` so the Chroma ranking is stable
    # across pages of the same query. We slice the result list to the
    # current page in memory; `total` reports the full hit count.
    over_fetch = page * page_size
    raw = await _vector_store.query(
        collection="articles",
        query_embedding=qvec,
        top_k=over_fetch,
        where=where,
    )

    # Hydrate Article rows from PG
    ids = [r["id"] for r in raw]
    if not ids:
        return SearchResponse(
            results=[], took_ms=int((time.time() - start) * 1000),
            page=page, page_size=page_size, total=0,
        )

    from uuid import UUID as _UUID

    res = await db.execute(
        select(Article).where(Article.id.in_([_UUID(i) for i in ids]))
    )
    articles_by_id = {str(a.id): a for a in res.scalars().all()}

    # Build the full ranked list, then slice the requested page.
    full_results: list[SearchResult] = []
    for hit in raw:
        a = articles_by_id.get(hit["id"])
        if a is None:
            continue
        full_results.append(
            SearchResult(
                article=ArticleOut.model_validate(a),
                score=hit["score"],
                highlights=[],
            )
        )

    total = len(full_results)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_slice = full_results[start_idx:end_idx]

    return SearchResponse(
        results=page_slice,
        took_ms=int((time.time() - start) * 1000),
        page=page,
        page_size=page_size,
        total=total,
    )
