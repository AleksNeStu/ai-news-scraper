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


@pytest.fixture
def fake_embedder(monkeypatch):
    embedder = MagicMock(spec=ArticleEmbedder)
    embedder.embed = AsyncMock(return_value=[0.0] * 1536)
    monkeypatch.setattr("api.routers.search._embedder", embedder)
    return embedder


@pytest.fixture
def fake_vector_store(monkeypatch):
    store = MagicMock(spec=ChromaVectorStore)

    async def query(collection, query_embedding, top_k, where=None):
        # `top_k` here is the over-fetch (page * page_size). Return the
        # first `top_k` deterministic hits so the router can slice.
        return [
            {
                "id": str(uuid4()),
                "score": 1.0 - (i * 0.001),
                "document": None,
                "metadata": {},
            }
            for i in range(top_k)
        ]

    store.query = AsyncMock(side_effect=query)
    monkeypatch.setattr("api.routers/search._vector_store", store)
    return store


@pytest.fixture
def fake_articles(monkeypatch):
    """A pool of Article rows keyed by id; only those referenced by the
    vector-store hits are queried for in the hydration step.

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

    async def fake_execute(stmt):
        ids = []
        for c in (
            stmt.whereclause.children
            if hasattr(stmt.whereclause, "children")
            else [stmt.whereclause]
        ):
            ids.extend(c.value)
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
    # fake_vector_store returns top_k = 1 * 10 = 10 hits
    assert body["total"] == 10
    assert len(body["results"]) == 10


@pytest.mark.asyncio
async def test_search_explicit_page_2_returns_correct_slice(client_with_overrides):
    r = await client_with_overrides.post(
        "/search", json={"query": "ai", "page": 2, "page_size": 5}
    )
    body = r.json()
    assert body["page"] == 2
    assert body["page_size"] == 5
    assert body["total"] == 10  # 2 * 5 = 10 over-fetched
    assert len(body["results"]) == 5


@pytest.mark.asyncio
async def test_search_page_beyond_range_returns_empty_with_total(client_with_overrides):
    r = await client_with_overrides.post(
        "/search", json={"query": "ai", "page": 99, "page_size": 10}
    )
    body = r.json()
    assert body["page"] == 99
    assert body["page_size"] == 10
    assert body["total"] == 10
    assert body["results"] == []


@pytest.mark.asyncio
async def test_search_top_k_is_accepted_as_page_size_synonym(client_with_overrides):
    r = await client_with_overrides.post("/search", json={"query": "ai", "top_k": 7})
    body = r.json()
    assert body["page_size"] == 7
    assert body["total"] == 7
    assert len(body["results"]) == 7


@pytest.mark.asyncio
async def test_search_page_size_wins_when_both_are_set(client_with_overrides):
    r = await client_with_overrides.post(
        "/search", json={"query": "ai", "top_k": 7, "page_size": 3}
    )
    body = r.json()
    assert body["page_size"] == 3
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_search_total_stable_across_pages(client_with_overrides):
    r1 = await client_with_overrides.post(
        "/search", json={"query": "ai", "page": 1, "page_size": 3}
    )
    r2 = await client_with_overrides.post(
        "/search", json={"query": "ai", "page": 2, "page_size": 3}
    )
    assert r1.json()["total"] == r2.json()["total"]
    assert r1.json()["total"] == 6  # 2 * 3 over-fetched


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
