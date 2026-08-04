"""Integration tests: ``POST /scrape`` propagates ``topics`` end-to-end.

The unit tests in ``test_topic_extractor.py`` cover the sanitize /
dedupe / sort / failure-mode pipeline. This file covers the
wiring contract: when ``_process_one`` produces an ``Article`` with
``topics``, the response (``ArticleOut``) carries the same list
byte-for-byte.

The LLM, scraper, summarizer, embedder, and vector store are all
mocked — the goal is to prove the route plumbs the field through,
not that any of those services work.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

os.environ.setdefault("DATABASE_NULL_POOL", "1")

import pytest
from httpx import ASGITransport, AsyncClient

from api.db.database import get_db
from api.deps import get_current_user_id
from api.main import app
from api.models.article import Article

_TEST_USER_ID = uuid4()
_TEST_HEADLINE = "Sample headline"
_TEST_URL = "https://example.com/sample-article"
_TEST_TOPICS = ["python", "rag", "release-notes"]


def _make_article(user_id: UUID, url: str, headline: str, topics: list[str]) -> Article:
    """Build a real Article ORM instance with a real UUID PK.

    Uses uuid4() for the PK + a fixed indexed_at so the response
    is fully deterministic across runs.
    """
    article = Article(
        id=uuid4(),
        user_id=user_id,
        url=url,
        headline=headline,
        body="<p>body</p>",
        summary="summary",
        topics=topics,
        source_domain="example.com",
        publish_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        indexed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    return article


@pytest.fixture
def scrape_client() -> Any:
    """AsyncClient with ``get_db`` + ``get_current_user_id`` overridden.

    The DB session is replaced with an AsyncMock — the route never
    touches the real DB because ``_process_one`` is patched at the
    module level (see the test body).
    """
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user_id] = lambda: _TEST_USER_ID
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_scrape_response_carries_extracted_topics(
    monkeypatch: Any, scrape_client: AsyncClient
) -> None:
    """End-to-end: mocked _process_one returns Article with topics;
    POST /scrape response (ArticleOut) preserves the list.

    This pins the wiring contract from ADR-026 §7. The unit tests
    in ``test_topic_extractor.py`` cover the sanitize pipeline;
    this test covers the route plumbing.
    """
    from api.routers import scrape as scrape_module

    async def _fake_process_one(
        url: str, user_id: UUID | None, db: Any
    ) -> Article:
        assert url == _TEST_URL
        assert user_id == _TEST_USER_ID
        return _make_article(user_id, url, _TEST_HEADLINE, _TEST_TOPICS)

    monkeypatch.setattr(scrape_module, "_process_one", _fake_process_one)

    async with scrape_client as client:
        resp = await client.post("/scrape", json={"url": _TEST_URL})

    assert resp.status_code == 201, resp.text
    body = resp.json()
    # ArticleOut.topics: list[str] — must match the list we injected.
    assert body["topics"] == _TEST_TOPICS
    # Sanity-check the rest of the ArticleOut contract.
    assert body["headline"] == _TEST_HEADLINE
    assert body["url"] == _TEST_URL
    assert body["source_domain"] == "example.com"


@pytest.mark.asyncio
async def test_scrape_response_with_empty_topics(
    monkeypatch: Any, scrape_client: AsyncClient
) -> None:
    """If the extractor yields [] (e.g. LLM failure, sanitization
    rejected all candidates), the response carries an empty list —
    NOT a 5xx. The scrape endpoint must never 5xx because of an
    extraction failure (ADR-026 §Failure mode).
    """
    from api.routers import scrape as scrape_module

    async def _fake_process_one(
        url: str, user_id: UUID | None, db: Any
    ) -> Article:
        return _make_article(user_id, url, _TEST_HEADLINE, [])

    monkeypatch.setattr(scrape_module, "_process_one", _fake_process_one)

    async with scrape_client as client:
        resp = await client.post("/scrape", json={"url": _TEST_URL})

    assert resp.status_code == 201, resp.text
    assert resp.json()["topics"] == []
