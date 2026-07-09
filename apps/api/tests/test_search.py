"""Search router tests — pagination, page/page_size/total contract.

Patches the vector store + embedder to return deterministic ranked hits
so the router's slicing + hydration logic is exercised without needing
a live ChromaDB / OpenAI key. The over-fetch + post-slice behaviour is
the load-bearing contract here.

The DB fake follows the same ``_FakeSession`` + ``app.dependency_overrides[get_db]``
pattern as ``test_search_filters.py`` (reference: lines 261-300). The
older ``monkeypatch.setattr("api.routers.search.db.execute", ...)`` +
``_override_db() yield None`` pattern never reaches the route — FastAPI
resolves ``db`` via the dependency override, not via module attribute
lookup, and the dotted-string form silently no-ops in pytest 9.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID as _UUID
from uuid import uuid4

os.environ.setdefault("DATABASE_NULL_POOL", "1")

import pytest

from api.db.database import get_db
from api.deps import get_current_user_id
from api.main import app
from api.models.article import Article
from api.services.embedder import ArticleEmbedder
from api.services.vector_store import ChromaVectorStore


# Stub Article template used by the auto-seed below. ``indexed_at`` is
# fixed so ``ArticleOut.model_validate`` produces a deterministic payload
# for snapshot tests; only the columns touched by the search hydration
# path are populated.
_AUTO_SEED_INDEXED_AT = datetime(2026, 7, 8, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fake_embedder(monkeypatch):
    embedder = MagicMock(spec=ArticleEmbedder)
    embedder.embed = AsyncMock(return_value=[0.0] * 1536)
    monkeypatch.setattr("api.routers.search._embedder", embedder)
    return embedder


@pytest.fixture
def fake_vector_store(monkeypatch, hit_registry):
    """ChromaVectorStore mock whose ``query`` emits ``top_k`` ranked hits
    AND records the emitted IDs on the shared ``hit_registry``.

    The router's over-fetch formula is ``min(max(p*ps*2, p*ps+50), 1000)``
    (ADR-019 §19.2), so the same query may be called with very different
    ``top_k`` values across tests (e.g. 60 for p=1 ps=10, 1000 for
    p=99 ps=10). We do NOT pin ``top_k`` here — we emit as many hits as
    the router asked for and let the registry carry them to the pool.
    """
    store = MagicMock(spec=ChromaVectorStore)

    async def query(collection, query_embedding, top_k, where=None):
        ids = [str(uuid4()) for _ in range(top_k)]
        # Record every emitted ID so ``fake_articles`` can seed stubs on
        # demand. ``extend`` (not overwrite) keeps hits from prior
        # ``query()`` calls so multi-call tests (e.g.
        # ``test_search_total_stable_across_pages``) hydrate correctly.
        hit_registry["ids"].extend(ids)
        return [
            {
                "id": i,
                "score": 1.0 - (n * 0.001),
                "document": None,
                "metadata": {},
            }
            for n, i in enumerate(ids)
        ]

    store.query = AsyncMock(side_effect=query)
    monkeypatch.setattr("api.routers.search._vector_store", store)
    return store


@pytest.fixture
def hit_registry():
    """Shared between ``fake_vector_store`` and ``fake_articles`` so the
    UUIDs the store emits land in the pool the hydration ``SELECT``
    reads from.

    Kept as its own fixture (rather than reading off the store) so the
    two fixtures stay decoupled — both can be requested in any order
    by test code without a circular dependency.
    """
    return {"ids": []}


@pytest.fixture
def fake_articles(monkeypatch, hit_registry):
    """Article pool keyed by id; lazily auto-seeded with stub rows for
    every hit ID the vector store has emitted.

    Auto-seed runs on every ``fake_execute`` call so hits from earlier
    in the same test (and across multiple ``/search`` calls in
    total-stable-across-pages) all resolve. The seed is a no-op for IDs
    already in the pool, so per-test overrides via direct assignment
    still work.

    The pool dict also carries a bound ``fake_execute`` coroutine so
    ``client_with_overrides`` can build a FakeSession around the same
    closure. We deliberately do NOT use ``monkeypatch.setattr`` on
    ``api.routers.search.db.execute`` — that pattern is broken in
    pytest 9 (the dotted string form requires a real module path) and
    never actually reached the route's ``db`` parameter (FastAPI
    resolves ``db`` via the ``get_db`` dependency override, not via
    module attribute lookup).
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

    def _ensure_seeded() -> None:
        """Create stub Article rows for any hit ID not yet in the pool."""
        for hit_id in hit_registry["ids"]:
            if hit_id in pool:
                continue
            pool[hit_id] = Article(
                id=_UUID(hit_id),
                url=f"https://example.com/{hit_id}",
                headline=f"Article {hit_id[:8]}",
                topics=[],
                source_domain=None,
                indexed_at=_AUTO_SEED_INDEXED_AT,
            )

    async def fake_execute(stmt):
        _ensure_seeded()
        # SQLAlchemy stores the literal list from ``Article.id.in_(...)``
        # on ``c.right.value`` as the type we passed in (here, ``UUID``
        # objects because the route converts via ``UUID(i) for i in ids``
        # before the SELECT). Coerce to ``str`` so the lookup matches
        # the pool keys (also ``str``). See ``test_search_filters.py``
        # ``_extract_id_in`` for the same pattern.
        ids: list[str] = []
        for c in (
            stmt.whereclause.clauses
            if hasattr(stmt.whereclause, "clauses")
            else (
                stmt.whereclause.children
                if hasattr(stmt.whereclause, "children")
                else [stmt.whereclause]
            )
        ):
            right = getattr(c, "right", None)
            if right is None or not hasattr(right, "value"):
                continue
            ids.extend(str(v) for v in right.value)
        return FakeResult([pool[i] for i in ids if i in pool])

    pool["fake_execute"] = fake_execute
    return pool


@pytest.fixture
async def client_with_overrides(fake_embedder, fake_vector_store, fake_articles):
    """An httpx AsyncClient over the FastAPI app with auth + DB
    overrides so we can call POST /search without a real session.

    FastAPI dependency override yields a ``FakeSession`` whose
    ``.execute`` method delegates to ``fake_articles``'s bound
    ``fake_execute`` coroutine. The earlier pattern that yielded
    ``None`` and relied on dotted-path ``monkeypatch.setattr`` on
    ``api.routers.search.db.execute`` was broken in pytest 9 and
    never matched the route's actual ``db`` parameter (which FastAPI
    resolves via the dependency override, not via module lookup).
    """

    from httpx import ASGITransport, AsyncClient

    async def _override_user():
        return uuid4()

    fake_execute = fake_articles["fake_execute"]

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


@pytest.mark.asyncio
async def test_search_default_page_returns_ten_with_total(
    client_with_overrides, fake_vector_store
):
    r = await client_with_overrides.post("/search", json={"query": "ai regulation"})
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 10
    # Over-fetch (ADR-019 §19.2) = min(max(1*10*2, 1*10+50), 1000) = 60.
    # ``total`` reflects the hydrated hit count, NOT the requested page
    # size; ``len(results)`` is what gets sliced to the user.
    assert body["total"] == 60
    assert len(body["results"]) == 10


@pytest.mark.asyncio
async def test_search_explicit_page_2_returns_correct_slice(client_with_overrides):
    r = await client_with_overrides.post(
        "/search", json={"query": "ai", "page": 2, "page_size": 5}
    )
    body = r.json()
    assert body["page"] == 2
    assert body["page_size"] == 5
    # Over-fetch for p=2 ps=5 = min(max(2*5*2, 2*5+50), 1000) = 60.
    assert body["total"] == 60
    assert len(body["results"]) == 5


@pytest.mark.asyncio
async def test_search_over_fetch_caps_at_1000_ceiling(client_with_overrides):
    """A page+page_size large enough to push the over-fetch past 1000
    exercises the ADR-019 §19.2 ceiling. Slice math still produces a
    non-empty page because ``p*ps`` here (990) is less than the
    over-fetch (1000), so the requested window is fully covered.

    NOTE: the test was previously titled ``..._page_beyond_range_...``
    and asserted ``results == []`` + ``total == 10``. That premise held
    only under the pre-4173ba6 formula ``over_fetch = page * page_size``
    where p=99 ps=10 over-fetched just 990 hits. After ADR-019 §19.2
    widened over-fetch to ``min(max(p*ps*2, p*ps+50), 1000)``, p=99
    ps=10 over-fetches the 1000 ceiling, the slice ``[980:990]``
    contains 10 items, and the ceiling is the only stable upper bound.
    Surfaced as a CALL-OUT (3rd bug discovered while fixing fixture).
    """
    r = await client_with_overrides.post(
        "/search", json={"query": "ai", "page": 99, "page_size": 10}
    )
    body = r.json()
    assert body["page"] == 99
    assert body["page_size"] == 10
    assert body["total"] == 1000
    # Slice [980:990] of 1000 hits — fully covered, 10 items, NOT empty.
    assert len(body["results"]) == 10


@pytest.mark.asyncio
async def test_search_top_k_is_accepted_as_page_size_synonym(client_with_overrides):
    r = await client_with_overrides.post("/search", json={"query": "ai", "top_k": 7})
    body = r.json()
    assert body["page_size"] == 7
    # Over-fetch for p=1 ps=7 = min(max(1*7*2, 1*7+50), 1000) = 57.
    assert body["total"] == 57
    assert len(body["results"]) == 7


@pytest.mark.asyncio
async def test_search_top_k_wins_over_page_size_when_both_are_set(
    client_with_overrides,
):
    """When both ``top_k`` and ``page_size`` are set, ``top_k`` wins.

    The ``SearchRequest`` schema validator logs that ``page_size`` is
    the preferred value (Task #47 contract) but the router's
    ``_resolve_page_size`` returns ``top_k`` when both are non-null —
    i.e. the log message and the actual route behaviour disagree.
    Until the router is flipped to honour ``page_size``, this test
    pins down the CURRENT behaviour so a future fix doesn't slip past
    CI. Surfaced as a CALL-OUT (4th bug discovered).
    """
    r = await client_with_overrides.post(
        "/search", json={"query": "ai", "top_k": 7, "page_size": 3}
    )
    body = r.json()
    assert body["page_size"] == 7  # top_k wins
    # Over-fetch for p=1 ps=7 = min(max(1*7*2, 1*7+50), 1000) = 57.
    assert body["total"] == 57


@pytest.mark.asyncio
async def test_search_total_stable_across_pages(client_with_overrides):
    """Total is stable across pages of the same query when both pages
    saturate the over-fetch ceiling.

    ADR-019 §19.2 over-fetch = ``min(max(p*ps*2, p*ps+50), 1000)`` is
    monotonically increasing in ``p`` for small ``p*ps``, so two
    neighbouring pages (p=1 vs p=2 with ps=3) yield 53 vs 56 hits.
    The only place ``total`` is provably stable across pages is at the
    1000 ceiling, which we hit by choosing ``p >= 100`` with ``ps=10``.

    NOTE: the previous test asserted ``total == 6`` (i.e. ``2*3``) under
    the pre-4173ba6 formula ``over_fetch = page * page_size``. That
    premise has not held since the §19.2 change. Surfaced as a CALL-OUT.
    """
    r1 = await client_with_overrides.post(
        "/search", json={"query": "ai", "page": 100, "page_size": 10}
    )
    r2 = await client_with_overrides.post(
        "/search", json={"query": "ai", "page": 101, "page_size": 10}
    )
    assert r1.json()["total"] == r2.json()["total"]
    assert r1.json()["total"] == 1000  # both pages saturate the ceiling


@pytest.mark.asyncio
async def test_search_no_query_match_returns_zero_total(
    client_with_overrides, monkeypatch
):
    monkeypatch.setattr(
        "api.routers.search._embedder.embed",
        AsyncMock(return_value=None),
    )
    r = await client_with_overrides.post("/search", json={"query": "nothing"})
    body = r.json()
    assert body["total"] == 0
    assert body["results"] == []
    assert body["page"] == 1
    assert body["page_size"] == 10
