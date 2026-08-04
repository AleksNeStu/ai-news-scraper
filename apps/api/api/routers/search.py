"""Search router — semantic + hybrid search with pagination + facets.

Filters (ADR-019 §19.7):
  - ``source`` is pushed into the Chroma ``where`` clause (scalar
    equality, native-supported).
  - ``topics`` and ``date_from``/``date_to`` are applied at the PG
    hydration step. The Chroma top-K is over-fetched using the formula
    in §19.2 so post-filter dropout does not empty a page.

Facets (ADR-020 / Task #53):
  - ``GET /search/facets`` returns per-dimension aggregations over the
    current user's library (sources, topics, date_range) used to
    populate the filter UI option lists. Redis-cached, 60s TTL.
"""

import logging
import time
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.deps import get_current_user_id
from api.models.article import Article
from api.schemas.article import ArticleOut
from api.schemas.search import (
    FacetsResponse,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from api.services import facet_cache
from api.services.embedder import ArticleEmbedder
from api.services.facet_aggregator import aggregate_facets
from api.services.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])

_embedder = ArticleEmbedder()
_vector_store = ChromaVectorStore()


def _resolve_page_size(payload: SearchRequest) -> int:
    """Effective page_size, honouring the deprecated `top_k` synonym.

    Per SearchRequest._no_both_top_k_and_page_size, callers that set
    both ``top_k`` and a non-default ``page_size`` are documented to
    prefer ``page_size`` (the validator logs the same). Previously the
    router inverted this and returned ``top_k`` -- a contract violation
    caught by Task #58 / Devil review. We honour the documented
    precedence: explicit ``page_size`` wins, ``top_k`` is a synonym
    used only when ``page_size`` is left at its default and ``top_k``
    is provided.
    """
    if payload.page_size != 10 and payload.page_size is not None:
        return payload.page_size
    if payload.top_k is not None:
        return payload.top_k
    return payload.page_size


def over_fetch_count(page: int, page_size: int) -> int:
    """Over-fetch width for ADR-019 §19.2.

    The formula: ``min(max(page * page_size * 2, page * page_size + 50), 1000)``.
    A 2x multiplier absorbs the expected PG hydration dropout when
    topics/date filters are applied; a +50 floor protects very early
    pages where 2x would under-fetch; the 1000 ceiling protects Chroma
    latency.

    Imported by ``tests/test_search.py`` so the suite references this
    single source of truth rather than re-deriving the formula
    in-line. Devil F2 (Task #59) -- changes here MUST co-change the
    test cases that consume the formula; the import is the lock.
    """
    return min(max(page * page_size * 2, page * page_size + 50), 1000)


def _build_hydration_clauses(filters: SearchFilters | None) -> list:
    """Extra WHERE clauses for the PG hydration step.

    Implements ADR-019 §19.7:
      - ``topics``: Postgres array overlap (``&&``) — OR semantics per
        §19.3. Empty list / None are no-ops.
      - ``date_from``: inclusive lower bound (``>=``).
      - ``date_to``: inclusive end-of-day — translated to a strict
        ``<`` comparison against ``date_to + 1 day`` so a user picking
        ``date_to=2026-07-08`` still matches articles indexed on that
        UTC day (§19.4).

    Returns a list of SQLAlchemy expressions; ANDed into the hydration
    ``select`` in left-to-right order.
    """
    if filters is None:
        return []
    clauses: list = []
    if filters.topics:
        # ``&& ARRAY[:topics]`` — "shares at least one element". Empty
        # list / None are short-circuited above.
        clauses.append(Article.topics.op("&&")(filters.topics))
    if filters.date_from is not None:
        clauses.append(Article.indexed_at >= filters.date_from)
    if filters.date_to is not None:
        # Inclusive end-of-day: compare strictly-less-than the next day.
        clauses.append(Article.indexed_at < (filters.date_to + timedelta(days=1)))
    return clauses


@router.post("", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    start = time.time()
    page = payload.page
    page_size = _resolve_page_size(payload)
    qvec = await _embedder.embed(payload.query)
    if qvec is None:
        return SearchResponse(
            results=[],
            took_ms=int((time.time() - start) * 1000),
            page=page,
            page_size=page_size,
            total=0,
        )

    where: dict = {"user_id": str(user_id)}
    if payload.filters and payload.filters.source:
        where["source_domain"] = payload.filters.source

    # Over-fetch (ADR-019 §19.2): page*page_size on early pages, with a
    # 50-item floor and a 2x multiplier on later pages to absorb the
    # expected PG hydration dropout when topics/date filters are
    # applied. The 1000 ceiling protects Chroma latency.
    # The formula is extracted to `over_fetch_count` so the test suite
    # can import the single source of truth (Devil F2 / Task #59).
    over_fetch = over_fetch_count(page, page_size)
    raw = await _vector_store.query(
        collection="articles",
        query_embedding=qvec,
        top_k=over_fetch,
        where=where,
    )

    # Hydrate Article rows from PG, then filter by topics / date range.
    ids = [r["id"] for r in raw]
    if not ids:
        return SearchResponse(
            results=[],
            took_ms=int((time.time() - start) * 1000),
            page=page,
            page_size=page_size,
            total=0,
        )

    extra_clauses = _build_hydration_clauses(payload.filters)
    stmt = select(Article).where(Article.id.in_([UUID(i) for i in ids]))
    for clause in extra_clauses:
        stmt = stmt.where(clause)
    res = await db.execute(stmt)
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


@router.get("/facets", response_model=FacetsResponse)
async def facets(
    response: Response,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Aggregate the current user's library along the three filter axes.

    Task #53 / ADR-020. Three per-dimension SQL queries are issued
    (sources / topics / date_range) and the union is wrapped in a
    60-second Redis cache keyed on ``facets:{user_id}``. The
    ``Cache-Control: private, max-age=60`` header lets the browser
    dedupe repeat requests inside the TTL window without violating
    the multi-tenant contract (the response is user-scoped, hence
    ``private`` not ``public``).

    Empty library returns all-zero counts with ``date_range.min =
    date_range.max = null`` so the front-end can render an "empty
    library" placeholder without special-casing 200-OK-with-empty-
    body versus 200-OK-with-data. The aggregator explicitly swallows
    per-dimension exceptions and degrades the affected dimension to
    an empty list rather than 500-ing the whole endpoint — see
    ``api.services.facet_aggregator.aggregate_facets`` docstring.
    """

    async def _compute() -> FacetsResponse:
        return await aggregate_facets(db, user_id)

    facets_resp, cache_hit = await facet_cache.get_or_compute(user_id, _compute)

    # Cache-Control headers — `private` (never proxy/CDN-share per-user
    # facets), `max-age=60` matches the Redis TTL so browser-side and
    # server-side caches share the same freshness window.
    response.headers["Cache-Control"] = (
        f"private, max-age={facet_cache.CACHE_TTL_SECONDS}"
    )
    # No `Vary` is set, deliberately (Task #53 Devil M-4). The facets
    # body varies ONLY by `user_id` (carried in the JWT, not a request
    # header) and by the (query, filters) pair — none of which are
    # represented as `Vary` axes. The response does NOT depend on
    # `Accept-Encoding` (server emits JSON only) or `Accept-Language`
    # (dimension labels are stable strings; the topic taxonomy is the
    # same for every locale in v1). `private` already prevents
    # cross-user sharing at shared caches, so adding `Vary: Authorization`
    # would be redundant. If a future revision wants to differentiate
    # logged-in vs anonymous facets (e.g. to broaden the topics for
    # anon users), that decision belongs in a follow-up ADR — NOT here.
    # Ops-only — `Vary` is not strictly needed (no Accept-Encoding based
    # negotiation here) but we mark the hit/miss so on-call can grep the
    # log; this header is NOT a contract.
    response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"

    return facets_resp
