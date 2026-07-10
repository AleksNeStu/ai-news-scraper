"""Facet aggregator — per-dimension counts over the current user's library.

Task #53 / ADR-020.

Three SQL statements, one per facet dimension:

  1. ``sources``  — ``SELECT source_domain, COUNT(*) FROM articles
                       WHERE user_id = :uid AND source_domain IS NOT NULL
                       GROUP BY source_domain ORDER BY COUNT(*) DESC``
  2. ``topics``   — ``SELECT topic, COUNT(DISTINCT articles.id) FROM articles
                       CROSS JOIN UNNEST(topics) AS topic
                       WHERE user_id = :uid
                       GROUP BY topic ORDER BY COUNT(DISTINCT articles.id) DESC``
                       (the ``DISTINCT`` is over the parent row, not
                       the unnested label)
  3. ``date_range`` — ``SELECT MIN(indexed_at), MAX(indexed_at) FROM articles
                         WHERE user_id = :uid``

All three are scoped to ``user_id`` so the response is multi-tenant safe
(no cross-user leakage even if Redis serves a stale cache from a
different user — see ADR-020 §20.4 on the per-user cache key).

Per-dimension queries are deliberate (Task #53 hard requirement). A
single ``GROUP BY source_domain, UNNEST(topics)`` would force PG to
materialize the cartesian product on the server side and couple the
latency of the cheap sources count to the slow topics unnest. The
fan-out design also lets us cache each dimension independently and
degrades gracefully — a failure on ``topics`` returns sources +
date_range with an empty topics list rather than failing the whole
response (see ``aggregate_facets``).

The aggregator returns a fully-populated ``FacetsResponse`` on every
call (empty lists / null date bounds when the library is empty) so the
route handler does not need to special-case "no articles".
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.article import Article
from api.schemas.search import FacetCount, FacetDateRange, FacetsResponse

logger = logging.getLogger(__name__)


async def _aggregate_sources(db: AsyncSession, user_id: UUID) -> list[FacetCount]:
    """Group by ``source_domain`` for the current user.

    NULL ``source_domain`` rows are excluded — a row without a domain
    cannot populate the source filter UI, and counting it would distort
    the per-bucket totals for the others. The SELECT itself is cheap
    (uses the ``ix_articles_source_domain`` index per the Article model
    declaration); we cap nothing because the source list is bounded by
    the number of distinct domains a single user scrapes from.
    """
    stmt = (
        select(Article.source_domain, func.count(Article.id).label("cnt"))
        .where(Article.user_id == user_id)
        .where(Article.source_domain.is_not(None))
        .group_by(Article.source_domain)
        .order_by(func.count(Article.id).desc())
    )
    res = await db.execute(stmt)
    return [FacetCount(value=row.source_domain, count=row.cnt) for row in res.all()]


async def _aggregate_topics(db: AsyncSession, user_id: UUID) -> list[FacetCount]:
    """Unnest ``articles.topics`` and group by the resulting label.

    ``Article.topics`` is a Postgres ``ARRAY(String)``. ``UNNEST`` on
    the column materialises the array elements as rows; the GROUP BY
    then collapses them per tag. The count is ``COUNT(DISTINCT
    articles.id)`` — not ``COUNT(*)`` — so each article contributes
    at most one per tag, regardless of whether its topics array
    contains a duplicate element (e.g. ``['ai', 'ai']`` from a
    buggy extractor or a future LLM run). The contract documented
    on ``FacetCount`` and on the TS JSDoc is "number of articles
    in the user's library that share this topic", so a duplicate
    tag on one article must count as 1, not 2.

    We deliberately do not cap the result: the topic taxonomy is
    LLM-generated per article (ADR-013) and naturally bounded to
    low single-digit totals per article, so even a heavy library
    produces a tractable distinct-topic list.

    Note: ``unnest`` is rendered via SQLAlchemy's ``func.unnest`` which
    expands the array column into a table-valued expression. The
    ``.alias("topic")`` is purely cosmetic — Postgres does not require
    a derived-table name for a CROSS JOIN with a function, but the
    named alias makes the rendered SQL self-documenting in logs.

    Casting ``DISTINCT`` over ``Article.id`` (the parent row, not the
    unnested label) is what makes the dedup work — casting over
    ``topic_col`` would dedupe identical tag strings across the full
    result set instead of collapsing same-article duplicates in the
    source array. The SQLAlchemy 2.x idiom is
    ``func.count(distinct(Article.id))`` — ``distinct`` is a unary
    expression wrapper, not a kwarg to ``count``.
    """
    topic_col = func.unnest(Article.topics).alias("topic")
    stmt = (
        select(topic_col, func.count(distinct(Article.id)).label("cnt"))
        .where(Article.user_id == user_id)
        # Filter PG NULL array elements (and NULL-unnest rows) so a
        # row with ``topics == NULL`` or an explicit NULL element does
        # not appear as the literal string "None" in the response.
        # Without this guard, ``str(row[0])`` happily coerces None to
        # ``"None"`` and a topic named "None" would be created. The
        # ``isnot(None)`` predicate is applied on the unnested column
        # itself so the per-element check rides on the same
        # ``CROSS JOIN LATERAL`` PG materialises for ``UNNEST``.
        .where(topic_col.isnot(None))
        .group_by(topic_col)
        .order_by(func.count(distinct(Article.id)).desc())
    )
    res = await db.execute(stmt)
    return [FacetCount(value=str(row[0]), count=row.cnt) for row in res.all()]


async def _aggregate_date_range(db: AsyncSession, user_id: UUID) -> FacetDateRange:
    """MIN/MAX of ``indexed_at`` for the current user.

    Returns ``{min: None, max: None}`` for an empty library (PG's
    ``MIN``/``MAX`` over zero rows yields NULL, not an error). This is
    the empty-library behaviour called out in Task #53: no 500, just
    a well-formed response with zero counts everywhere.
    """
    stmt = select(func.min(Article.indexed_at), func.max(Article.indexed_at)).where(
        Article.user_id == user_id
    )
    res = await db.execute(stmt)
    row = res.one()
    return FacetDateRange(min=row[0], max=row[1])


async def aggregate_facets(db: AsyncSession, user_id: UUID) -> FacetsResponse:
    """Run the three aggregations and assemble a ``FacetsResponse``.

    On a per-dimension exception we log + return an empty list for the
    failing dimension rather than failing the whole request. The route
    is read-only and used for filter UI population — a partial result
    is far more useful than a 500, and the next request (60s later,
    after the Redis TTL expires) will retry from scratch. We never
    silently swallow; each failure is logged with the user_id so an
    operator can grep for the impact.

    Why the three aggregations are SEQUENTIAL, not ``asyncio.gather``-ed
    (Task #53 Devil M-5): SQLAlchemy's ``AsyncSession`` is **not** safe
    for concurrent statements on the same instance. Issuing two
    ``await db.execute(stmt)`` calls in flight via ``asyncio.gather``
    races on the connection's transactional state and raises
    "this session is in 'committed' state" (or, more insidiously,
    interleaves result rows between the two queries — the kind of
    bug that passes tests but corrupts data in prod). Each dimension
    must ``await`` to completion before the next begins. The
    migration path to true concurrency is per-dimension
    ``async_sessionmaker()`` instances (each query gets its own
    session) — flagged in Task #53 / ADR-020 as a follow-up, not
    done here, because the current end-to-end latency on a 5k-row
    library is already <30 ms and the extra complexity is not yet
    earned.
    """
    # Sources — cheapest of the three; index on ``source_domain``
    # covers the WHERE + GROUP BY.
    try:
        sources = await _aggregate_sources(db, user_id)
    except Exception:
        logger.exception("facets: sources aggregation failed for user_id=%s", user_id)
        sources = []

    # Topics — uses UNNEST on an ARRAY column; no covering index, but
    # bounded by article count, so a 5k-article library scans ~5k rows
    # in <30ms on the dev DB.
    try:
        topics = await _aggregate_topics(db, user_id)
    except Exception:
        logger.exception("facets: topics aggregation failed for user_id=%s", user_id)
        topics = []

    # Date range — MIN/MAX over indexed_at; uses the per-column index.
    try:
        date_range = await _aggregate_date_range(db, user_id)
    except Exception:
        logger.exception(
            "facets: date_range aggregation failed for user_id=%s", user_id
        )
        date_range = FacetDateRange(min=None, max=None)

    return FacetsResponse(sources=sources, topics=topics, date_range=date_range)


__all__ = ["aggregate_facets"]
