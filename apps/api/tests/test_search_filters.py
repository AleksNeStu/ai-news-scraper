"""Search filter tests — server-side ``topics`` + ``date_from``/``date_to``
(ADR-019 §19.7, §19.10 T1–T17).

Reuses the embedder / vector-store overrides from ``test_search.py`` and
plugs in a richer ``fake_execute`` that enforces the extra hydration
clauses in Python. The router builds the ``select(Article).where(...)``
statement by ANDing in clauses for topics (``&& ARRAY[:topics]``) and
the date bounds; this fixture walks that statement tree and rejects any
pool entry that does not satisfy every predicate.

Without the in-Python filter, the hydration would return every article
in the pool keyed by ``id`` and the tests would pass falsely (the
router-side filter would never be exercised).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

os.environ.setdefault("DATABASE_NULL_POOL", "1")

import pytest

from api.db.database import get_db
from api.deps import get_current_user_id
from api.main import app
from api.models.article import Article
from api.services.embedder import ArticleEmbedder
from api.services.vector_store import ChromaVectorStore

# ---------------------------------------------------------------------------
# Pool helpers
# ---------------------------------------------------------------------------


def _make_article(
    article_id: str,
    *,
    topics: list[str] | None = None,
    indexed_at: datetime | None = None,
    source_domain: str | None = None,
    headline: str | None = None,
) -> Article:
    """Build an Article ORM instance with the filterable fields set.

    Only the columns touched by ADR-019 filters are populated. The rest
    are left at SQLAlchemy defaults so ``ArticleOut.model_validate``
    still produces a valid payload.
    """
    return Article(
        id=article_id,
        url=f"https://example.com/{article_id}",
        headline=headline or f"Article {article_id[:8]}",
        body=None,
        summary=None,
        topics=list(topics or []),
        source_domain=source_domain,
        indexed_at=indexed_at or datetime(2026, 7, 8, 10, 0, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Shared fixtures (subset of ``test_search.py``)
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_embedder(monkeypatch):
    embedder = MagicMock(spec=ArticleEmbedder)
    embedder.embed = AsyncMock(return_value=[0.0] * 1536)
    monkeypatch.setattr("api.routers.search._embedder", embedder)
    return embedder


@pytest.fixture
def fake_vector_store(monkeypatch):
    """A vector store whose hit list is built from a per-test ``pool``.

    The store reads ``_search_pool`` off its own attributes (set in
    each test). Each hit has ``id`` matching a pool key, with a
    descending score so the slice in the router preserves ordering.

    Honors ``where["source_domain"]`` (the only Chroma-level filter
    wired by ADR-019 §19.1) by trimming the pool before emitting hits.
    Topics + date bounds are PG-side and enforced by the
    ``article_pool`` fixture's ``_eval_extra_filters``.
    """
    store = MagicMock(spec=ChromaVectorStore)
    store._pool_meta: dict[str, dict] = {}  # id → metadata

    async def query(collection, query_embedding, top_k, where=None):
        pool: list[str] = list(store._search_pool)
        if where and "source_domain" in where:
            wanted = where["source_domain"]
            pool = [
                pid
                for pid in pool
                if store._pool_meta.get(pid, {}).get("source_domain") == wanted
            ]
        return [
            {
                "id": pool[i],
                "score": 1.0 - (i * 0.001),
                "document": None,
                "metadata": store._pool_meta.get(pool[i], {}),
            }
            for i in range(min(top_k, len(pool)))
        ]

    store.query = AsyncMock(side_effect=query)
    store._search_pool = []  # default; tests override
    monkeypatch.setattr("api.routers.search._vector_store", store)
    return store


@pytest.fixture
def article_pool(monkeypatch):
    """In-memory article pool keyed by id, plus a fake DB executor.

    The executor walks the hydration statement's WHERE clauses and
    keeps only entries that satisfy every predicate. This mirrors the
    SQL behaviour for ``Article.topics && ARRAY[:t]`` and
    ``Article.indexed_at >= date_from AND indexed_at < (date_to + 1d)``
    well enough for unit tests.
    """
    pool: dict[str, Article] = {}

    class FakeResult:
        def __init__(self, articles):
            self._articles = articles

        def scalars(self):
            class _Scalars:
                def __init__(self, arts):
                    self._arts = arts

                def all(self):
                    return self._arts

            return _Scalars(self._articles)

    def _is_id_clause(c) -> bool:
        """True if the predicate is on ``articles.id``.

        SQLAlchemy creates a fresh ``InstrumentedAttribute`` for every
        ``Article.<col>`` access, so identity comparison (``is``)
        against ``Article.id`` always returns False across module
        boundaries. We compare by ``key`` and ``table.name`` instead.
        """
        left = getattr(c, "left", None)
        if left is None:
            return False
        return bool(
            getattr(left, "key", None) == "id"
            and getattr(getattr(left, "table", None), "name", None) == "articles"
        )

    def _clauses_of(stmt):
        """Return the iterable of WHERE predicates for ``stmt``.

        SQLAlchemy exposes the predicate list as ``.clauses`` on a
        ``BooleanClauseList`` and as the object itself when only a
        single predicate is set. Falls back to ``.children`` for older
        SQLAlchemy versions that exposed the alias.
        """
        clause = stmt.whereclause
        cs = getattr(clause, "clauses", None)
        if cs:
            return list(cs)
        children = getattr(clause, "children", None)
        if children:
            return list(children)
        return [clause]

    def _extract_id_in(stmt):
        """Pull the literal id list out of the leading ``id IN (...)``."""
        for c in _clauses_of(stmt):
            if _is_id_clause(c) and getattr(c, "right", None) is not None:
                return [str(v) for v in c.right.value]
        return []

    def _eval_extra_filters(stmt, candidate: Article) -> bool:
        """Apply every non-id predicate in the WHERE tree in Python.

        The walker matches predicates by ``left.key`` (column identity)
        rather than by rendered-SQL substring, except for the topics
        ``&&`` operator which uses a custom ``custom_op`` whose operator
        function identity doesn't reveal the symbol — for that one we
        additionally require ``&&`` in the rendered SQL so a typo
        (e.g. swapping ``&&`` for ``@>`` in a refactor) is caught
        instead of silently falling through the "keep everything"
        branch.
        """
        for c in _clauses_of(stmt):
            if _is_id_clause(c):
                continue
            right = c.right
            sql_text = str(c)
            left_key = getattr(getattr(c, "left", None), "key", None)
            # Topics: must be on the ``topics`` column AND use ``&&``
            # overlap (not ``@>`` containment — see ADR-019 section 19.3
            # for the OR-vs-AND semantics decision). Catching a
            # refactor that swaps the operator is part of the test
            # contract per Devil MAJOR-1 / MINOR-1 post-hoc review.
            if left_key == "topics":
                if "&&" not in sql_text:
                    # Wrong operator (or no operator) on the topics
                    # column — fail loud rather than silently keeping
                    # the row, which would mask the regression.
                    raise AssertionError(
                        f"Expected '&&' in topics clause, got: {sql_text!r}"
                    )
                wanted = right.value if hasattr(right, "value") else list(right)
                if not any(t in candidate.topics for t in wanted):
                    return False
                continue
            # Date bounds: ``Article.indexed_at >= bound`` /
            # ``Article.indexed_at < bound`` — match on left.key plus
            # the operator function name.
            op_name = c.operator.__name__ if hasattr(c, "operator") else ""
            if left_key == "indexed_at" and op_name == "ge":
                bound = right.value if hasattr(right, "value") else right
                if not (candidate.indexed_at >= bound):
                    return False
                continue
            if left_key == "indexed_at" and op_name == "lt":
                bound = right.value if hasattr(right, "value") else right
                if not (candidate.indexed_at < bound):
                    return False
                continue
            # Unknown operator: don't drop anything (safer than the
            # inverse for backward compat).
        return True

    async def fake_execute(stmt):
        wanted_ids = _extract_id_in(stmt)
        out = []
        for aid in wanted_ids:
            a = pool.get(aid)
            if a is None:
                continue
            if _eval_extra_filters(stmt, a):
                out.append(a)
        return FakeResult(out)

    # Carry the bound coroutine on the pool dict so ``client_with_overrides``
    # can build a FakeSession around it. We do NOT use ``monkeypatch.setattr``
    # on ``api.routers.search.db.execute`` — that pattern is broken in
    # pytest 9 (the dotted string form requires a real module path) and
    # never actually reached the route's ``db`` parameter (FastAPI
    # resolves ``db`` via the ``get_db`` dependency override, not via
    # module attribute lookup).
    pool["fake_execute"] = fake_execute
    return pool


@pytest.fixture
async def client_with_overrides(fake_embedder, fake_vector_store, article_pool):
    """httpx AsyncClient with auth + DB overrides wired up.

    FastAPI dependency override yields a ``FakeSession`` whose
    ``.execute`` method delegates to the pool-filtered
    ``fake_execute`` (built in ``article_pool``). The earlier pattern
    that yielded ``None`` and relied on dotted-path ``monkeypatch.setattr``
    on ``api.routers.search.db.execute`` was broken in pytest 9 and
    never matched the route's actual ``db`` parameter (which FastAPI
    resolves via the dependency override, not via module lookup).
    """
    from httpx import ASGITransport, AsyncClient

    async def _override_user():
        return uuid4()

    # ``article_pool`` is a dict that also carries the bound
    # ``fake_execute`` coroutine; we look it up here so the
    # FakeSession instance captures the same closure.
    fake_execute = article_pool["fake_execute"]

    class _FakeSession:
        async def execute(self, stmt):
            return await fake_execute(stmt)

        async def close(self):
            return None

    async def _override_db():
        yield _FakeSession()

    app.dependency_overrides[get_current_user_id] = _override_user
    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


def _seed_pool_and_hits(
    pool: dict[str, Article],
    store,
    *,
    articles: list[Article],
) -> None:
    """Register articles in the pool and arm the vector store to return
    them in the given order. Also copies each article's ``source_domain``
    into the store's metadata map so the source-domain Chroma-where
    filter has data to filter on."""
    for a in articles:
        pool[str(a.id)] = a
        store._pool_meta[str(a.id)] = {"source_domain": a.source_domain}
    store._search_pool = [str(a.id) for a in articles]


# ---------------------------------------------------------------------------
# T1–T5: Topics filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T1_single_topic_hit_with_that_topic_included(
    client_with_overrides, article_pool, fake_vector_store
):
    """T1: ``topics=['ai']`` and the hit is tagged ``['ai','ml']`` — overlap
    operator matches, hit is included."""
    aid = uuid4()
    a = _make_article(str(aid), topics=["ai", "ml"])
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={"query": "ai", "filters": {"topics": ["ai"]}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["article"]["id"] == str(aid)


@pytest.mark.asyncio
async def test_T2_multi_topic_or_semantics_overlap_matches_single_topic_article(
    client_with_overrides, article_pool, fake_vector_store
):
    """T2: ``topics=['ai','ml']`` and the hit is tagged ``['ml']`` —
    overlap (OR) matches, hit is included."""
    aid = uuid4()
    a = _make_article(str(aid), topics=["ml"])
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={"query": "x", "filters": {"topics": ["ai", "ml"]}},
    )
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["article"]["id"] == str(aid)


@pytest.mark.asyncio
async def test_T3_unrelated_topic_excluded(
    client_with_overrides, article_pool, fake_vector_store
):
    """T3: ``topics=['ai']`` and the hit is tagged ``['nlp']`` —
    overlap fails, hit is excluded (``total==0``)."""
    aid = uuid4()
    a = _make_article(str(aid), topics=["nlp"])
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={"query": "x", "filters": {"topics": ["ai"]}},
    )
    body = r.json()
    assert body["total"] == 0
    assert body["results"] == []


@pytest.mark.asyncio
async def test_T4_empty_topics_list_treated_as_no_filter(
    client_with_overrides, article_pool, fake_vector_store
):
    """T4: ``topics=[]`` — the router skips the clause (truthy check),
    so every hit passes through."""
    aid = uuid4()
    a = _make_article(str(aid), topics=["nlp"])
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={"query": "x", "filters": {"topics": []}},
    )
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["article"]["id"] == str(aid)


@pytest.mark.asyncio
async def test_T5_no_filter_preserves_existing_behaviour(
    client_with_overrides, article_pool, fake_vector_store
):
    """T5: no filters at all — every pool entry that matches its id is
    returned, identical to today."""
    aids = [uuid4() for _ in range(3)]
    arts = [_make_article(str(aid), topics=["ai"]) for aid in aids]
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=arts)
    r = await client_with_overrides.post("/search", json={"query": "ai"})
    body = r.json()
    assert body["total"] == 3
    assert {item["article"]["id"] for item in body["results"]} == {str(a) for a in aids}


# ---------------------------------------------------------------------------
# T6–T11: Date range filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T6_date_from_inclusive_at_midnight(
    client_with_overrides, article_pool, fake_vector_store
):
    """T6: ``date_from='2026-07-01'`` and ``indexed_at=2026-07-01T00:00:00Z``
    — ``>=`` keeps the row."""
    aid = uuid4()
    a = _make_article(
        str(aid),
        indexed_at=datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "filters": {"date_from": "2026-07-01T00:00:00Z"},
        },
    )
    body = r.json()
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_T7_date_from_excludes_prior_millisecond(
    client_with_overrides, article_pool, fake_vector_store
):
    """T7: ``date_from='2026-07-01'`` and ``indexed_at='2026-06-30T23:59:59Z'``
    — out of range, dropped."""
    aid = uuid4()
    a = _make_article(
        str(aid),
        indexed_at=datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc),
    )
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "filters": {"date_from": "2026-07-01T00:00:00Z"},
        },
    )
    body = r.json()
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_T8_date_to_inclusive_at_end_of_day(
    client_with_overrides, article_pool, fake_vector_store
):
    """T8: ``date_to='2026-07-08'`` and ``indexed_at=2026-07-08T23:59:59Z``
    — translated to ``< 2026-07-09``, kept."""
    aid = uuid4()
    a = _make_article(
        str(aid),
        indexed_at=datetime(2026, 7, 8, 23, 59, 59, tzinfo=timezone.utc),
    )
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "filters": {"date_to": "2026-07-08T00:00:00Z"},
        },
    )
    body = r.json()
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_T9_date_to_excludes_next_day_midnight(
    client_with_overrides, article_pool, fake_vector_store
):
    """T9: ``date_to='2026-07-08'`` and ``indexed_at=2026-07-09T00:00:00Z``
    — out of range, dropped."""
    aid = uuid4()
    a = _make_article(
        str(aid),
        indexed_at=datetime(2026, 7, 9, 0, 0, 0, tzinfo=timezone.utc),
    )
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "filters": {"date_to": "2026-07-08T00:00:00Z"},
        },
    )
    body = r.json()
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_T10_date_from_only(
    client_with_overrides, article_pool, fake_vector_store
):
    """T10: only ``date_from`` set — no ``date_to`` clause, future rows
    are not dropped."""
    aid_old = uuid4()
    aid_new = uuid4()
    old = _make_article(
        str(aid_old),
        indexed_at=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    new = _make_article(
        str(aid_new),
        indexed_at=datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc),
    )
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[old, new])
    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "filters": {"date_from": "2026-07-01T00:00:00Z"},
        },
    )
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["article"]["id"] == str(aid_new)


@pytest.mark.asyncio
async def test_T11_date_to_only(client_with_overrides, article_pool, fake_vector_store):
    """T11: only ``date_to`` set — no ``date_from`` clause, older rows
    are not dropped."""
    aid_old = uuid4()
    aid_new = uuid4()
    old = _make_article(
        str(aid_old),
        indexed_at=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    new = _make_article(
        str(aid_new),
        indexed_at=datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc),
    )
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[old, new])
    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "filters": {"date_to": "2026-06-30T00:00:00Z"},
        },
    )
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["article"]["id"] == str(aid_old)


# ---------------------------------------------------------------------------
# T12: Combined filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T12_combined_source_and_topics_intersection(
    client_with_overrides, article_pool, fake_vector_store
):
    """T12: ``source='x.com'`` + ``topics=['ai']`` — both clauses apply,
    only the intersection passes."""
    aid_pass = uuid4()
    aid_topic_fail = uuid4()
    aid_source_fail = uuid4()
    pass_ = _make_article(str(aid_pass), topics=["ai"], source_domain="x.com")
    topic_fail = _make_article(
        str(aid_topic_fail), topics=["nlp"], source_domain="x.com"
    )
    source_fail = _make_article(
        str(aid_source_fail), topics=["ai"], source_domain="y.com"
    )
    _seed_pool_and_hits(
        article_pool,
        fake_vector_store,
        articles=[pass_, topic_fail, source_fail],
    )
    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "filters": {"source": "x.com", "topics": ["ai"]},
        },
    )
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["article"]["id"] == str(aid_pass)


# ---------------------------------------------------------------------------
# T13: Over-fetch saturation at 1000 cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T13_over_fetch_saturates_at_1000_cap(
    client_with_overrides, fake_vector_store
):
    """T13: ``page * page_size * 2 > 1000`` ⇒ top_k = 1000.

    With page=100, page_size=10: page*page_size*2 = 2000 → cap to 1000.
    """
    fake_vector_store._search_pool = []
    await client_with_overrides.post(
        "/search",
        json={"query": "x", "page": 100, "page_size": 10},
    )
    fake_vector_store.query.assert_called_once()
    call_kwargs = fake_vector_store.query.call_args.kwargs
    assert call_kwargs["top_k"] == 1000


@pytest.mark.asyncio
async def test_over_fetch_uses_2x_multiplier_on_later_pages(
    client_with_overrides, fake_vector_store
):
    """Sanity: page=5, page_size=20 → 5*20*2 = 200, above the page*page_size+50=150 floor."""
    fake_vector_store._search_pool = []
    await client_with_overrides.post(
        "/search",
        json={"query": "x", "page": 5, "page_size": 20},
    )
    call_kwargs = fake_vector_store.query.call_args.kwargs
    assert call_kwargs["top_k"] == 200


@pytest.mark.asyncio
async def test_over_fetch_uses_floor_on_first_page(
    client_with_overrides, fake_vector_store
):
    """Sanity: page=1, page_size=10 → page*page_size*2=20 below the +50 floor."""
    fake_vector_store._search_pool = []
    await client_with_overrides.post(
        "/search",
        json={"query": "x", "page": 1, "page_size": 10},
    )
    call_kwargs = fake_vector_store.query.call_args.kwargs
    assert call_kwargs["top_k"] == 60  # 1*10 + 50


# ---------------------------------------------------------------------------
# T14–T16: Pydantic cross-field validator (schema-level, no router needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T14_inverted_dates_raise_422(client_with_overrides):
    """T14: ``SearchFilters(date_to < date_from)`` — FastAPI rejects with 422.

    Acceptance criterion #7 from ``docs/acceptance/task-52-search-filters.md``:
    the 422 body must surface the filter location (``loc == ["body",
    "filters"]``) and a ``value_error`` type code. Combined with the
    cross-field validator on ``SearchFilters`` (ADR-019 section 19.5),
    this verifies that the cross-field check fired - a refactor that
    accidentally disables the model-validator would no longer match the
    ``loc == ["body", "filters"]`` contract and would fail this test.
    """
    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "filters": {
                "date_from": "2026-07-08T00:00:00Z",
                "date_to": "2026-07-01T00:00:00Z",
            },
        },
    )
    assert r.status_code == 422
    body = r.json()
    # The project's exception handler at ``api.main`` wraps the
    # Pydantic errors list in a problem+json envelope under
    # ``context.errors`` (not the FastAPI-default ``detail``). Walk
    # that envelope to find the structured error per AC #7.
    errs = body.get("context", {}).get("errors") or body.get("detail")
    assert errs, body
    # Find the error whose ``loc`` points at the filters payload.
    err = next((e for e in errs if e.get("loc", [None])[-1] == "filters"), None)
    assert err is not None, body
    # ``loc`` is ``["body", "filters"]`` for a top-level validator on
    # the SearchFilters model.
    assert err["loc"] == ["body", "filters"], err
    # Pydantic renders ``PydanticCustomError("value_error", ...)`` as
    # ``type == "value_error"`` (the second positional argument
    # becomes the message and the first becomes the type code).
    assert err["type"] == "value_error", err
    # Message contains the rule the cross-field validator enforces.
    assert "date_to" in err["msg"], err


@pytest.mark.asyncio
async def test_T15_only_date_from_is_valid(
    client_with_overrides, article_pool, fake_vector_store
):
    """T15: only ``date_from`` set — validation passes, only one bound applied."""
    aid = uuid4()
    a = _make_article(
        str(aid),
        indexed_at=datetime(2026, 7, 8, 10, 0, 0, tzinfo=timezone.utc),
    )
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "filters": {"date_from": "2026-01-01T00:00:00Z"},
        },
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_T16_empty_filter_object_is_valid(
    client_with_overrides, article_pool, fake_vector_store
):
    """T16: empty filter object — validation passes, behaves like no filter."""
    aid = uuid4()
    a = _make_article(str(aid), topics=["nlp"])
    _seed_pool_and_hits(article_pool, fake_vector_store, articles=[a])
    r = await client_with_overrides.post(
        "/search",
        json={"query": "x", "filters": {}},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 1


# ---------------------------------------------------------------------------
# T17: Page 2 with topics filter that drops 50%
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T17_topics_filter_with_dropout_fills_page_2(
    client_with_overrides, article_pool, fake_vector_store
):
    """T17: 20 hits, half tagged 'ai', half tagged 'nlp'; topics=['ai']
    drops 10. Over-fetch formula must fetch enough that page 2 of a
    4-item page still returns the second slice of the filtered set.

    This exercises the §19.2 over-fetch formula on later pages:
    page=2, page_size=4 requires 8 post-filter items, but with 50%
    selectivity we need 16+ raw hits. The fake vector store is told
    to return up to ``top_k`` ids (the over-fetch); the PG hydration
    filter then keeps exactly the ai-tagged subset. Standard slicing
    of the post-filter set gives 4 items for both pages.
    """
    ai_ids = [uuid4() for _ in range(10)]
    nlp_ids = [uuid4() for _ in range(10)]
    pool_articles = [_make_article(str(aid), topics=["ai"]) for aid in ai_ids] + [
        _make_article(str(aid), topics=["nlp"]) for aid in nlp_ids
    ]
    for a in pool_articles:
        article_pool[str(a.id)] = a
    # Vector store returns ALL 20 ids in the original ordering — the
    # PG hydration filter then drops the 10 nlp rows.
    fake_vector_store._search_pool = [str(a.id) for a in pool_articles]

    r1 = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "page": 1,
            "page_size": 4,
            "filters": {"topics": ["ai"]},
        },
    )
    body1 = r1.json()
    assert body1["total"] == 10
    assert len(body1["results"]) == 4
    page1_ids = {item["article"]["id"] for item in body1["results"]}

    r2 = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "page": 2,
            "page_size": 4,
            "filters": {"topics": ["ai"]},
        },
    )
    body2 = r2.json()
    assert body2["total"] == 10
    assert len(body2["results"]) == 4
    page2_ids = {item["article"]["id"] for item in body2["results"]}

    r3 = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "page": 3,
            "page_size": 4,
            "filters": {"topics": ["ai"]},
        },
    )
    body3 = r3.json()
    assert body3["total"] == 10
    assert len(body3["results"]) == 2  # last page is partial
    page3_ids = {item["article"]["id"] for item in body3["results"]}

    # All three pages are disjoint, all are ai-tagged, and they cover
    # the entire ai-tagged subset (10 of 20 articles). This is the
    # over-fetch + page-slicing contract: the §19.2 over-fetch formula
    # (effective = min(max(page * page_size * 2, page * page_size + 50),
    # 1000)) fetches enough that page 2 of a 50%-selectivity filter
    # still has 4 hits to slice from.
    expected_ai = {str(a) for a in ai_ids}
    assert page1_ids.isdisjoint(page2_ids)
    assert page1_ids.isdisjoint(page3_ids)
    assert page2_ids.isdisjoint(page3_ids)
    assert page1_ids | page2_ids | page3_ids == expected_ai
    # nlp items must not leak into any page.
    expected_nlp = {str(n) for n in nlp_ids}
    all_returned = page1_ids | page2_ids | page3_ids
    assert all_returned.isdisjoint(expected_nlp)


# ---------------------------------------------------------------------------
# AC #8 + zero-match safety (Devil MAJOR-2 follow-up)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagination_total_reflects_filtered_count(
    client_with_overrides, article_pool, fake_vector_store
):
    """AC #8 verbatim: 25 candidates all tagged 'ai', page_size=10.
    Pages 1/2/3 report total=25 and slice sizes 10/10/5.

    Catches the regression where ``total`` is computed from the raw
    Chroma hit count (``len(raw)``) rather than the post-hydration
    filtered set (``len(full_results)``) — the docstring on
    ``_build_hydration_clauses`` warns about this contract; this test
    is the gate.
    """
    ai_ids = [uuid4() for _ in range(25)]
    pool_articles = [_make_article(str(aid), topics=["ai"]) for aid in ai_ids]
    for a in pool_articles:
        article_pool[str(a.id)] = a
    fake_vector_store._search_pool = [str(a.id) for a in pool_articles]

    expected_total = 25
    for page, expected_len in [(1, 10), (2, 10), (3, 5)]:
        r = await client_with_overrides.post(
            "/search",
            json={
                "query": "x",
                "page": page,
                "page_size": 10,
                "filters": {"topics": ["ai"]},
            },
        )
        body = r.json()
        assert body["total"] == expected_total, (
            f"page {page}: expected total={expected_total}, got {body['total']}"
        )
        assert len(body["results"]) == expected_len, (
            f"page {page}: expected {expected_len} results, got {len(body['results'])}"
        )


@pytest.mark.asyncio
async def test_filter_drops_all_candidates_returns_empty_with_zero_total(
    client_with_overrides, article_pool, fake_vector_store
):
    """Zero-match safety: filter eliminates every candidate.
    ``total == 0``, ``results == []``, no 5xx.

    Devil MINOR / Devil MAJOR-2 follow-up: AC #6 ("Zero / omitted
    filters") covers the no-filter baseline; this complements it by
    asserting the upper edge — filter that matches nothing — returns
    the same well-formed response shape, not an internal error.
    """
    # Pool: 5 articles, none tagged "ai". Filter "topics=['ai']"
    # should drop every one of them.
    aids = [uuid4() for _ in range(5)]
    pool_articles = [_make_article(str(aid), topics=["nlp"]) for aid in aids]
    for a in pool_articles:
        article_pool[str(a.id)] = a
    fake_vector_store._search_pool = [str(a.id) for a in pool_articles]

    r = await client_with_overrides.post(
        "/search",
        json={
            "query": "x",
            "page": 1,
            "page_size": 10,
            "filters": {"topics": ["ai"]},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["results"] == []
