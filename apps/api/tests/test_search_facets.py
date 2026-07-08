"""Tests for ``GET /search/facets`` (Task #53 / ADR-020).

Coverage:

  * Empty library returns well-formed zero counts (no 500).
  * Single-article library produces a 1-bucket result for each
    dimension.
  * Mixed library: sources / topics sorted DESC by count, date_range
    min/max bracketing the population.
  * Cache hit / miss: ``X-Cache`` header flips between MISS (first
    call) and HIT (second call inside the TTL). Cache key includes
    ``user_id`` — two different users hit the aggregator independently.
  * User isolation: two users with disjoint libraries see disjoint
    facets.

Fake Redis strategy: we replace ``facet_cache._client`` (module
private — accepted test-only coupling) with an in-memory ``dict``
that mimics the ``get`` / ``set`` / ``delete`` subset of the Redis
async API the cache wrapper touches. This avoids the real
``fakeredis`` package dependency (sandbox cannot install) and keeps
the test fully hermetic — no network, no fixture cleanup.

Fake DB strategy: a ``FakeSession`` that classifies the statement
by inspecting its ``select(...)`` columns (function name + column
key + table name) — NOT by rendering SQL to a string. String-based
classifiers break on cosmetic SQLAlchemy refactors (alias renames,
``literal_binds`` differences); column inspection is robust because
the aggregator only reads positional/attribute indices off the
returned rows. The user_id filter is enforced in Python so multi-
user isolation tests actually exercise the per-user scoping.
"""

from __future__ import annotations

import os
from collections import namedtuple
from datetime import datetime, timezone
from uuid import UUID, uuid4

os.environ.setdefault("DATABASE_NULL_POOL", "1")

import pytest

from api.db.database import get_db
from api.deps import get_current_user_id
from api.main import app
from api.models.article import Article
from api.services import facet_cache


# ---------------------------------------------------------------------------
# In-memory Redis fake (test-env safe)
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Tiny in-memory drop-in for the redis async client.

    Implements only the methods ``facet_cache`` calls:
    ``get(key)``, ``set(key, value, ex=...)``, ``delete(key)``.
    Methods return awaitables so the cache's ``await client.foo(...)``
    pattern keeps working without a real redis driver.
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: int = 0
        self.get_calls: int = 0

    async def get(self, key: str):
        self.get_calls += 1
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.set_calls += 1
        # ``ex=0`` in real Redis means "expire immediately" — the
        # value is set and then deleted before the next ``get`` returns.
        # T7 uses ``monkeypatch.setattr(facet_cache, "CACHE_TTL_SECONDS",
        # 0)`` to simulate TTL elapsing between two requests; without
        # honouring ``ex`` the second request would still HIT.
        if ex == 0:
            self.store.pop(key, None)
            return True
        self.store[key] = value
        return True

    async def delete(self, key: str):
        self.store.pop(key, None)
        return True


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis(monkeypatch):
    """Wire an in-memory Redis fake into ``facet_cache``.

    The cache wrapper lazily builds its client on first use; we
    monkeypatch ``facet_cache._get_redis`` so the lazy builder returns
    our fake. ``_reset_for_tests`` clears the module-cached client
    before each test so the fake takes effect on the very first
    cache call (not the second one).
    """
    facet_cache._reset_for_tests()
    fake = _FakeRedis()
    monkeypatch.setattr(facet_cache, "_get_redis", lambda: fake)
    yield fake
    facet_cache._reset_for_tests()


@pytest.fixture
def articles_pool() -> dict[str, Article]:
    """Per-test article pool keyed by id.

    The aggregation is purely on Article columns; we store a dict of
    fake ``Article`` instances and let the FakeSession walk them in
    Python. The pool is intentionally a separate fixture (not
    monkeypatched onto a module) so each test builds a fresh,
    self-contained library.
    """
    return {}


def _make_article(
    aid: UUID,
    *,
    source_domain: str | None = None,
    topics: list[str] | None = None,
    indexed_at: datetime | None = None,
    user_id: UUID | None = None,
) -> Article:
    """Build an Article ORM instance.

    ``user_id`` is part of the public surface because the FakeSession
    must filter by it (mirroring the production ``WHERE user_id = :uid``
    clause). Multi-user isolation tests rely on each article being
    owned by exactly one user; single-user tests pass a single uid and
    expect every seeded article to match.
    """
    return Article(
        id=aid,
        url=f"https://example.com/{aid}",
        headline=f"Article {str(aid)[:8]}",
        body=None,
        summary=None,
        topics=list(topics or []),
        source_domain=source_domain,
        indexed_at=indexed_at or datetime(2026, 7, 8, 10, 0, 0, tzinfo=timezone.utc),
        user_id=user_id,
    )


@pytest.fixture
def fake_session_factory(articles_pool):
    """Build a FakeSession that routes the three facet queries to the pool.

    The aggregator (``api.services.facet_aggregator``) issues three SQL
    statements that we classify by inspecting the ``select(...)``
    columns — not by rendering the SQL to a string. String-based
    classifiers break on cosmetic SQLAlchemy refactors (alias renames,
    ``literal_binds`` differences); column inspection is robust
    because the aggregator only reads positional/attribute indices
    off the returned rows.

    Classification:
      * Topics: statement contains a ``Function`` whose ``name ==
        'unnest'`` — matches the unnest-and-group-by on
        ``Article.topics``.
      * Sources: statement selects a non-function column whose
        ``key == 'source_domain'`` AND ``table.name == 'articles'``.
      * Date range: statement contains BOTH ``Function(name='min')``
        AND ``Function(name='max')`` over the indexed_at column.
    """

    def _build_session(uid: UUID):
        pool = articles_pool

        # Mimic SQLAlchemy ``Row`` — supports attribute access
        # (``row.source_domain``, ``row.cnt``) AND index access
        # (``row[0]``, ``row[1]``). The aggregator uses both styles
        # across the three queries, so the fake must match.
        _SourceRow = namedtuple("_SourceRow", ["source_domain", "cnt"])
        _TopicRow = namedtuple("_TopicRow", ["topic", "cnt"])

        class FakeResult:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

            def one(self):
                # Single-row aggregates (MIN/MAX) yield one row;
                # SQLAlchemy's ``one()`` returns a Row that supports
                # both attribute AND index access. We return a fresh
                # tuple so ``row[0]`` / ``row[1]`` reads work; for an
                # empty result we return ``[None, None]`` so
                # ``res.one()`` returns the sentinel without raising
                # ``NoResultFound``.
                return self._rows[0] if self._rows else (None, None)

        def _walk_for_func(stmt, name):
            """True iff any column expression or its wrapped element
            is a SQLAlchemy ``Function`` with ``.name == name``."""
            cols = stmt.column_descriptions
            for c in cols:
                expr = c["expr"]
                # ``func.unnest(Article.topics)`` is exposed as a
                # ``Function`` at the top level (when not aliased)
                # or wrapped in an Alias. The function's ``.name``
                # attribute is the string literal the SQL would
                # render ('unnest', 'min', 'max').
                if getattr(expr, "name", None) == name:
                    return True
                inner = getattr(expr, "element", None)
                if getattr(inner, "name", None) == name:
                    return True
            return False

        def _has_article_column(stmt, key: str) -> bool:
            cols = stmt.column_descriptions
            for c in cols:
                expr = c["expr"]
                if getattr(expr, "key", None) != key:
                    continue
                table = getattr(expr, "table", None)
                if table is None:
                    continue
                if getattr(table, "name", None) == "articles":
                    return True
            return False

        class FakeSession:
            def __init__(self):
                self._uid = uid

            def _own_articles(self):
                """Filter the pool to the current user's articles.

                Mirrors the production ``WHERE user_id = :uid`` clause
                on every aggregation. Without this filter, multi-user
                isolation tests would see cross-user data — defeating
                the entire point of the user_id-scoped key.
                """
                return [a for a in pool.values() if a.user_id == self._uid]

            async def execute(self, stmt):
                own = self._own_articles()
                # Topics unnest — detect the ``unnest`` function call.
                # Counts are DISTINCT-articles (mirrors the production
                # ``COUNT(DISTINCT articles.id)`` — see Devil review C1):
                # one article with ``topics=['ai','ai']`` contributes
                # at most 1 to the ``ai`` bucket, not 2.
                if _walk_for_func(stmt, "unnest"):
                    counts: dict[str, int] = {}
                    for a in own:
                        seen_for_this_article: set[str] = set()
                        for t in a.topics or []:
                            if t in seen_for_this_article:
                                continue
                            seen_for_this_article.add(t)
                            counts[t] = counts.get(t, 0) + 1
                    raw_rows = sorted(
                        counts.items(),
                        key=lambda kv: (-kv[1], kv[0]),
                    )
                    rows = [_TopicRow(topic=k, cnt=v) for k, v in raw_rows]
                    return FakeResult(rows)
                # Sources — selects Article.source_domain (a Column).
                if _has_article_column(stmt, "source_domain"):
                    counts = {}
                    for a in own:
                        if a.source_domain is None:
                            continue
                        counts[a.source_domain] = counts.get(a.source_domain, 0) + 1
                    raw_rows = sorted(
                        counts.items(),
                        key=lambda kv: (-kv[1], kv[0]),
                    )
                    rows = [_SourceRow(source_domain=k, cnt=v) for k, v in raw_rows]
                    return FakeResult(rows)
                # Date range — MIN + MAX over indexed_at.
                if _walk_for_func(stmt, "min") and _walk_for_func(stmt, "max"):
                    indexed = [a.indexed_at for a in own if a.indexed_at is not None]
                    if not indexed:
                        return FakeResult([(None, None)])
                    return FakeResult([(min(indexed), max(indexed))])
                # Unknown statement — return empty so a refactor that
                # introduces a new query is visible (the aggregator
                # would raise rather than silently serving zeros).
                return FakeResult([])

            async def close(self):
                return None

        return FakeSession()

    return _build_session


@pytest.fixture(scope="function", loop_scope="function")
async def client_for_user(fake_redis, fake_session_factory):
    """Per-user httpx AsyncClient factory.

    Yields an async callable ``client_for(uid) -> AsyncClient`` that
    creates a fresh, properly-closed httpx client for the given user
    UUID. The cache fake is shared across clients, but each client
    gets its own FakeSession with the right user_id, so two-user
    isolation tests can swap in a second client without bleeding
    state.

    Save/restore on ``app.dependency_overrides`` makes the context
    manager safe to nest — T5 holds two clients open at once (one
    per user) and the inner client's exit must restore the outer
    client's overrides, not clear them. ``async with`` is also
    load-bearing for httpx: without it the underlying ASGI
    transport leaks across tests.
    """
    from contextlib import asynccontextmanager

    from httpx import ASGITransport, AsyncClient

    @asynccontextmanager
    async def _build_client(uid: UUID):
        async def _override_user():
            return uid

        async def _override_db():
            yield fake_session_factory(uid)

        # Save any pre-existing override so nested contexts restore
        # the outer's view on exit. Without this, the inner client's
        # ``app.dependency_overrides.clear()`` on its exit path would
        # wipe the outer's overrides and every request in the outer
        # would 401.
        prev_user = app.dependency_overrides.get(get_current_user_id)
        prev_db = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_current_user_id] = _override_user
        app.dependency_overrides[get_db] = _override_db
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
        finally:
            # Restore the pre-entry state (or remove the key) so the
            # outer's overrides are still in effect after we exit.
            if prev_user is None:
                app.dependency_overrides.pop(get_current_user_id, None)
            else:
                app.dependency_overrides[get_current_user_id] = prev_user
            if prev_db is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = prev_db

    yield _build_client

    # Last-resort cleanup: if a test exited without closing the
    # context manager, drop everything so the next test starts clean.
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T1 — Empty library
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T1_empty_library_returns_zero_counts(client_for_user):
    """No articles → all-zero counts, null date_range, 200 OK.

    Devil MAJOR-style safety: the endpoint must NEVER 500 just because
    the user has not scraped anything yet. PG MIN/MAX over zero rows
    yields NULL — the aggregator must surface that as ``min=null,
    max=null`` rather than raising.
    """
    async with client_for_user(uuid4()) as c:
        r = await c.get("/search/facets")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sources"] == []
    assert body["topics"] == []
    assert body["date_range"] == {"min": None, "max": None}


# ---------------------------------------------------------------------------
# T2 — Single article library
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T2_single_article_populates_one_bucket_per_dimension(
    client_for_user, articles_pool
):
    aid = uuid4()
    user = uuid4()
    a = _make_article(
        aid,
        source_domain="nytimes.com",
        topics=["ai", "policy"],
        indexed_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        user_id=user,
    )
    articles_pool[str(aid)] = a

    async with client_for_user(user) as c:
        r = await c.get("/search/facets")
    assert r.status_code == 200
    body = r.json()
    assert body["sources"] == [{"value": "nytimes.com", "count": 1}]
    # topics sorted DESC by count, then ASC by value for stability.
    assert body["topics"] == [
        {"value": "ai", "count": 1},
        {"value": "policy", "count": 1},
    ]
    assert body["date_range"]["min"] == "2026-07-01T12:00:00Z"
    assert body["date_range"]["max"] == "2026-07-01T12:00:00Z"


# ---------------------------------------------------------------------------
# T3 — Mixed library: sorting + bracketing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T3_mixed_library_sorted_desc_by_count_with_brackets(
    client_for_user, articles_pool
):
    """Multiple articles: sources / topics sorted DESC; date_range
    min/max span the population (NOT all-same)."""
    user = uuid4()
    arts = [
        _make_article(
            uuid4(),
            source_domain="nytimes.com",
            topics=["ai", "ml"],
            indexed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            user_id=user,
        ),
        _make_article(
            uuid4(),
            source_domain="wired.com",
            topics=["ai", "policy"],
            indexed_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
            user_id=user,
        ),
        _make_article(
            uuid4(),
            source_domain="wired.com",
            topics=["ai"],
            indexed_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
            user_id=user,
        ),
        _make_article(
            uuid4(),
            source_domain="theverge.com",
            topics=["ai"],
            indexed_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
            user_id=user,
        ),
    ]
    for a in arts:
        articles_pool[str(a.id)] = a

    async with client_for_user(user) as c:
        r = await c.get("/search/facets")
    assert r.status_code == 200
    body = r.json()

    # Sources: wired.com (2), nytimes.com (1), theverge.com (1)
    assert body["sources"] == [
        {"value": "wired.com", "count": 2},
        {"value": "nytimes.com", "count": 1},
        {"value": "theverge.com", "count": 1},
    ]
    # Topics: ai (4), ml (1), policy (1)
    assert body["topics"] == [
        {"value": "ai", "count": 4},
        {"value": "ml", "count": 1},
        {"value": "policy", "count": 1},
    ]
    # Date range: bracketing the population.
    assert body["date_range"]["min"] == "2026-06-01T00:00:00Z"
    assert body["date_range"]["max"] == "2026-07-08T00:00:00Z"


# ---------------------------------------------------------------------------
# T4 — Cache MISS then HIT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T4_cache_miss_then_hit_within_ttl(
    client_for_user, articles_pool, fake_redis
):
    """First call: MISS (cache empty, aggregator runs, response cached).
    Second call inside TTL: HIT (cache serves, aggregator NOT called).
    """
    aid = uuid4()
    user = uuid4()
    articles_pool[str(aid)] = _make_article(
        aid, source_domain="wired.com", topics=["ai"], user_id=user
    )
    async with client_for_user(user) as c:
        r1 = await c.get("/search/facets")
        assert r1.status_code == 200
        assert r1.headers["x-cache"] == "MISS"
        assert r1.headers["cache-control"] == "private, max-age=60"
        # After the first call, the cache must hold exactly one key.
        assert len(fake_redis.store) == 1
        assert fake_redis.set_calls == 1

        r2 = await c.get("/search/facets")
        assert r2.status_code == 200
        assert r2.headers["x-cache"] == "HIT"
        # Same body served from cache — set_calls must NOT increment.
        assert fake_redis.set_calls == 1
        assert r2.json() == r1.json()


# ---------------------------------------------------------------------------
# T5 — user_id isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T5_two_users_with_disjoint_libraries_see_disjoint_facets(
    client_for_user, articles_pool, fake_redis
):
    """Two users in the same pool. Each must see ONLY their own articles.

    Even though the cache shares one Redis instance, the cache key is
    per-user (``facets:{user_id}``) — so a HIT for user A cannot leak
    to user B. This is the multi-tenant safety net called out in
    ADR-020 §20.4.
    """
    user_a = uuid4()
    user_b = uuid4()

    a_art = _make_article(
        uuid4(),
        source_domain="nytimes.com",
        topics=["ai"],
        indexed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        user_id=user_a,
    )
    b_art = _make_article(
        uuid4(),
        source_domain="wired.com",
        topics=["ml"],
        indexed_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
        user_id=user_b,
    )
    articles_pool[str(a_art.id)] = a_art
    articles_pool[str(b_art.id)] = b_art

    async with client_for_user(user_a) as ca:
        async with client_for_user(user_b) as cb:
            ra = await ca.get("/search/facets")
            rb = await cb.get("/search/facets")

    assert ra.status_code == 200
    assert rb.status_code == 200

    body_a = ra.json()
    body_b = rb.json()

    # Sources are completely disjoint — user A sees only nytimes.com,
    # user B sees only wired.com.
    assert [s["value"] for s in body_a["sources"]] == ["nytimes.com"]
    assert [s["value"] for s in body_b["sources"]] == ["wired.com"]
    # Topics are disjoint too.
    assert [t["value"] for t in body_a["topics"]] == ["ai"]
    assert [t["value"] for t in body_b["topics"]] == ["ml"]

    # Cache should now hold two distinct keys (one per user).
    keys = list(fake_redis.store.keys())
    assert any(str(user_a) in k for k in keys)
    assert any(str(user_b) in k for k in keys)


# ---------------------------------------------------------------------------
# T6 — Cache key includes user_id (not the response)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T6_cache_keys_are_user_scoped(
    client_for_user, articles_pool, fake_redis
):
    """Three calls, three distinct users → three distinct cache keys.

    Catches a regression where the cache key is computed without the
    user_id suffix (e.g. ``facets:global``) and a stale entry from
    user X silently serves user Y. The fixture-level Redis fake is
    shared, so we can inspect the store directly.
    """
    # Seed one article per user so each request actually populates the
    # cache (the cache miss path writes; miss-on-empty returns
    # ``sources=[]`` and still writes, so the per-user key is created
    # either way — but seeding makes the assertion about distinct
    # keys obvious in any failure trace).
    for uid_idx in range(3):
        u = uuid4()
        a = _make_article(
            uuid4(),
            source_domain=f"src{uid_idx}.com",
            topics=["x"],
            user_id=u,
        )
        articles_pool[str(a.id)] = a
        async with client_for_user(u) as c:
            r = await c.get("/search/facets")
        assert r.status_code == 200
        assert r.headers["x-cache"] == "MISS"

    # Three distinct keys, all under the ``facets:`` prefix.
    keys = sorted(fake_redis.store.keys())
    assert len(keys) == 3
    assert all(k.startswith("facets:") for k in keys)
    # Distinct UUIDs in the suffix.
    suffixes = {k.split(":", 1)[1] for k in keys}
    assert len(suffixes) == 3


# ---------------------------------------------------------------------------
# T1b — Devil C1: duplicate topic inside a single article counts once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T1b_duplicate_topic_in_single_article_counts_as_one(
    client_for_user, articles_pool
):
    """One article with ``topics=['ai', 'ai']`` — contract says 1, not 2.

    Devil review (FIX-C1): ``COUNT(*)`` over unnested rows returns 2,
    which contradicts the ``FacetCount`` JSDoc contract ("count =
    number of articles in the user's library that share this topic").
    A buggy extractor or a future LLM run can produce duplicate tags
    inside one article's array; the aggregator must collapse them
    via ``COUNT(DISTINCT articles.id)``.
    """
    aid = uuid4()
    user = uuid4()
    a = _make_article(
        aid,
        source_domain="reuters.com",
        topics=["ai", "ai"],  # duplicate on purpose
        indexed_at=datetime(2026, 7, 5, 8, 30, 0, tzinfo=timezone.utc),
        user_id=user,
    )
    articles_pool[str(aid)] = a

    async with client_for_user(user) as c:
        r = await c.get("/search/facets")
    assert r.status_code == 200, r.text
    body = r.json()
    # One bucket, count=1 — the duplicate tag is collapsed.
    assert body["topics"] == [{"value": "ai", "count": 1}]
    # Sources / date_range untouched.
    assert body["sources"] == [{"value": "reuters.com", "count": 1}]
    assert body["date_range"]["min"] == "2026-07-05T08:30:00Z"
    assert body["date_range"]["max"] == "2026-07-05T08:30:00Z"


# ---------------------------------------------------------------------------
# T7 — Devil H3: cache MISS after TTL expiry recomputes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T7_cache_miss_after_ttl_recomputes(
    client_for_user, articles_pool, fake_redis, monkeypatch
):
    """Two calls: first MISS writes with TTL=0 → entry is gone → second MISS.

    Devil review (FIX-H3): AC #7 requires a regression guard for TTL
    expiry. We force expiry by collapsing the TTL to 0 between calls
    via ``monkeypatch.setattr(facet_cache, "CACHE_TTL_SECONDS", 0)``;
    the FakeRedis honours ``ex=0`` by NOT persisting the entry, which
    is the contract Redis itself implements for ``SET key val EX 0``
    (immediate expiry). A regression that breaks TTL handling — e.g.
    dropping the ``ex=`` kwarg in ``_try_set_cached`` — would surface
    here as a HIT on the second call.
    """
    aid = uuid4()
    user = uuid4()
    articles_pool[str(aid)] = _make_article(
        aid, source_domain="bbc.com", topics=["climate"], user_id=user
    )

    async with client_for_user(user) as c:
        # Force TTL=0 for both calls — first call still MISSes (cache
        # empty), writes an ex=0 entry that the FakeRedis immediately
        # drops; second call MISSes again because the cache stayed
        # empty.
        monkeypatch.setattr(facet_cache, "CACHE_TTL_SECONDS", 0)
        r1 = await c.get("/search/facets")
        assert r1.status_code == 200
        assert r1.headers["x-cache"] == "MISS"
        # The FakeRedis.set was called once but the entry was dropped
        # because ex=0; the store stays empty.
        assert fake_redis.set_calls == 1
        assert fake_redis.store == {}

        r2 = await c.get("/search/facets")
        assert r2.status_code == 200
        # Crucial assertion: the second call is ALSO MISS, because the
        # previous entry was expired on write. set_calls incremented
        # again, proving the recompute path ran.
        assert r2.headers["x-cache"] == "MISS"
        assert fake_redis.set_calls == 2


# ---------------------------------------------------------------------------
# T8 — Devil H4: unauthenticated request returns 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_T8_unauthenticated_returns_401():
    """No auth override → ``get_current_user_id`` raises → 401.

    Devil review (FIX-H4): the route declares
    ``Depends(get_current_user_id)``, so a missing override is the
    single regression vector that turns the facets endpoint into a
    cross-user data leak. This test pins the dependency in place by
    hitting the app WITHOUT the user-id override and asserting 401.

    We deliberately do NOT parameterise this test on
    ``client_for_user`` because that fixture installs the auth
    override at the moment of fixture instantiation — i.e. it
    pollutes ``app.dependency_overrides`` globally for the test
    even before our body runs. Rolling our own async context manager
    here lets us install a DB override (so the request reaches the
    route handler) while leaving ``get_current_user_id`` at the
    production wiring that 401s when no token is present.
    """
    from contextlib import asynccontextmanager

    from httpx import ASGITransport, AsyncClient

    @asynccontextmanager
    async def _raw_client():
        async def _override_db():
            # Never reached — 401 fires before any query runs. Yielding
            # a None session keeps the dep well-formed so FastAPI's
            # dependency-injection machinery does not raise a different
            # error first.
            yield None

        prev_user = app.dependency_overrides.get(get_current_user_id)
        prev_db = app.dependency_overrides.get(get_db)
        # Explicitly DO NOT install a get_current_user_id override —
        # the production wiring raises HTTPException(401) when neither
        # an Authorization header nor the auth cookie is present.
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides[get_db] = _override_db
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
        finally:
            if prev_user is None:
                app.dependency_overrides.pop(get_current_user_id, None)
            else:
                app.dependency_overrides[get_current_user_id] = prev_user
            if prev_db is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = prev_db

    async with _raw_client() as c:
        r = await c.get("/search/facets")
    # The auth dep (``api.deps.get_current_user_id`` →
    # ``_extract_token``) raises HTTPException(401) when neither an
    # Authorization header nor the auth cookie is present. Pin the
    # code so a regression that drops the dep would show up here
    # (the route would then return 200 and the body would contain
    # the facets payload — fail loud, fail fast).
    assert r.status_code == 401, r.text
    body = r.json()
    # The auth dep's body shape is ``detail-only``; we pin that the
    # facets-specific keys are NOT in the response — i.e. the route
    # handler never ran.
    assert "sources" not in body
    assert "topics" not in body
    assert "date_range" not in body
