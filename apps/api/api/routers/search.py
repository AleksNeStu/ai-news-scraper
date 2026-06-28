"""Search router — semantic + hybrid search."""

import logging
import time
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
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
_settings = get_settings()

_embedder = ArticleEmbedder(
    api_key=_settings.openai_api_key,
    model=_settings.openai_embedding_model,
    dimensions=_settings.embedding_dimensions,
)
_vector_store = ChromaVectorStore()


@router.post("", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    start = time.time()
    qvec = await _embedder.embed(payload.query)
    if qvec is None:
        return SearchResponse(results=[], took_ms=int((time.time() - start) * 1000))

    where: dict = {"user_id": str(user_id)}
    if payload.filters and payload.filters.source:
        where["source_domain"] = payload.filters.source

    raw = await _vector_store.query(
        collection="articles",
        query_embedding=qvec,
        top_k=payload.top_k,
        where=where,
    )

    # Hydrate Article rows from PG
    ids = [r["id"] for r in raw]
    if not ids:
        return SearchResponse(results=[], took_ms=int((time.time() - start) * 1000))

    from uuid import UUID as _UUID

    res = await db.execute(
        select(Article).where(Article.id.in_([_UUID(i) for i in ids]))
    )
    articles_by_id = {str(a.id): a for a in res.scalars().all()}

    results: list[SearchResult] = []
    for hit in raw:
        a = articles_by_id.get(hit["id"])
        if a is None:
            continue
        results.append(
            SearchResult(
                article=ArticleOut.model_validate(a),
                score=hit["score"],
                highlights=[],
            )
        )
    return SearchResponse(results=results, took_ms=int((time.time() - start) * 1000))
