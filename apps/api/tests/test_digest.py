"""Tests for the digest service + clustering pipeline (Task #8, ADR-012).

Coverage (per the brief):

* Clustering fail-soft — when the LLM raises, ``cluster_user_articles``
  returns a single chronological cluster rather than propagating.
* Clustering fall-back on parse error — bad JSON from the LLM still
  yields a cluster, never crashes.
* Idempotency of ``generate_digest`` — calling it twice for the same
  ``(user, date)`` returns the same row (no LLM call the second time).
* Tenant isolation — user B's digest is not visible to user A.

The DB-dependent assertions use the ``db_session`` fixture; the LLM
provider is monkeypatched so no real OpenAI/Gemini call is made.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from api.models.article import Article
from api.models.digest import Digest, Notification
from api.models.user import User
from api.services.auth import hash_password
from api.services.clustering import (
    ClusterResult,
    _parse_cluster_response,
    cluster_user_articles,
)
from api.services.digest import generate_digest


# ---------------------------------------------------------------------------
# Helpers — local builders that don't touch the lifecycle of the
# shared `auth_user` fixture (which commits via a different connection).
# ---------------------------------------------------------------------------


async def _make_user(session, email: str = "u@example.com") -> User:
    user = User(email=email, hashed_password=hash_password("testpassword123"))
    session.add(user)
    await session.flush()
    return user


def _make_article(
    session,
    user: User,
    *,
    headline: str,
    summary: str = "Lead paragraph that is reasonably long. " * 4,
    indexed_at: datetime | None = None,
) -> Article:
    a = Article(
        user_id=user.id,
        url=f"https://example.test/{headline[:20].replace(' ', '-')}",
        headline=headline,
        body="body text",
        summary=summary,
        topics=["ai"],
        source_domain="example.test",
        indexed_at=indexed_at or datetime.now(timezone.utc),
    )
    session.add(a)
    return a


def _patch_openai_client(monkeypatch: pytest.MonkeyPatch, fake: MagicMock) -> None:
    """Stub the brief-path OpenAI client on the modules that build it.

    Per ADR-012 §12.5 the brief path uses ``gpt-4o-mini`` DIRECTLY
    (not ``get_llm_provider()``), so the seam to mock is the module
    ``_openai_client()`` factory on both services.
    """
    from api.services import clustering as clustering_module
    from api.services import digest as digest_module

    monkeypatch.setattr(clustering_module, "_openai_client", lambda: fake)
    monkeypatch.setattr(digest_module, "_openai_client", lambda: fake)


def _resp(text: str) -> MagicMock:
    """Shape of one ``chat.completions.create`` response.

    The service code reads ``response.choices[0].message.content`` — we
    need exactly that attribute path populated.
    """
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    return response


# ---------------------------------------------------------------------------
# Clustering — pure-function tests (no DB required)
# ---------------------------------------------------------------------------


def test_parse_cluster_response_valid() -> None:
    """A well-formed LLM response parses to clusters with the right indices."""
    raw = json.dumps(
        [
            {"topic": "EU AI Act", "article_indices": [0, 1]},
            {"topic": "Funding", "article_indices": [2]},
        ]
    )
    parsed = _parse_cluster_response(raw, n_articles=3)
    assert parsed is not None
    assert [p.topic for p in parsed] == ["EU AI Act", "Funding"]
    assert [p.indices for p in parsed] == [[0, 1], [2]]


def test_parse_cluster_response_tolerates_code_fence() -> None:
    """Markdown code fences around JSON are stripped before parsing."""
    raw = '```json\n[{"topic":"A","article_indices":[0]}]\n```'
    parsed = _parse_cluster_response(raw, n_articles=1)
    assert parsed is not None
    assert parsed[0].topic == "A"


def test_parse_cluster_response_missing_indices_returns_none() -> None:
    """If not every input index appears, treat as a parse failure."""
    raw = json.dumps([{"topic": "A", "article_indices": [0]}])  # index 1 missing
    assert _parse_cluster_response(raw, n_articles=2) is None


def test_parse_cluster_response_duplicate_indices_returns_none() -> None:
    """If the LLM double-assigns an index, refuse it."""
    raw = json.dumps(
        [
            {"topic": "A", "article_indices": [0, 1]},
            {"topic": "B", "article_indices": [0]},  # 0 already used
        ]
    )
    assert _parse_cluster_response(raw, n_articles=2) is None


def test_parse_cluster_response_invalid_json_returns_none() -> None:
    """Non-JSON or non-list payloads return ``None``."""
    assert _parse_cluster_response("not json", n_articles=3) is None
    assert _parse_cluster_response(json.dumps({"oops": 1}), n_articles=1) is None
    assert _parse_cluster_response("", n_articles=3) is None


# ---------------------------------------------------------------------------
# Clustering — DB-driven, fail-soft behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_user_articles_falls_back_when_llm_raises(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM raising → single chronological cluster, no exception raised."""
    from api.services import clustering as clustering_module

    user = await _make_user(db_session, email="c1@example.com")
    base = datetime(2026, 6, 29, 10, 0, tzinfo=timezone.utc)
    for i in range(3):
        _make_article(
            db_session,
            user,
            headline=f"Headline {i}",
            indexed_at=base + timedelta(minutes=i),
        )
    await db_session.flush()

    fake = MagicMock()
    fake.chat.completions.create = AsyncMock(side_effect=RuntimeError("LLM offline"))
    monkeypatch.setattr(clustering_module, "_openai_client", lambda: fake)

    clusters = await cluster_user_articles(db_session, user.id, date(2026, 6, 29))
    assert len(clusters) == 1
    assert clusters[0].cluster_id == "today"
    assert len(clusters[0].article_ids) == 3


@pytest.mark.asyncio
async def test_cluster_user_articles_falls_back_on_parse_error(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM responding with non-JSON → still returns a single cluster."""
    from api.services import clustering as clustering_module

    user = await _make_user(db_session, email="c2@example.com")
    base = datetime(2026, 6, 29, 11, 0, tzinfo=timezone.utc)
    _make_article(db_session, user, headline="A", indexed_at=base)
    _make_article(
        db_session, user, headline="B", indexed_at=base + timedelta(minutes=5)
    )
    await db_session.flush()

    fake = MagicMock()
    fake.chat.completions.create = AsyncMock(return_value=_resp("not really json"))
    monkeypatch.setattr(clustering_module, "_openai_client", lambda: fake)

    clusters = await cluster_user_articles(db_session, user.id, date(2026, 6, 29))
    assert len(clusters) == 1
    assert clusters[0].article_ids  # fell back, didn't drop articles


@pytest.mark.asyncio
async def test_cluster_user_articles_empty_window_returns_empty(
    db_session,
) -> None:
    """No articles in the 24h window → ``[]``."""
    user = await _make_user(db_session, email="c3@example.com")
    clusters = await cluster_user_articles(db_session, user.id, date(2026, 6, 29))
    assert clusters == []


# ---------------------------------------------------------------------------
# generate_digest — idempotency + tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_digest_idempotent_per_user_date(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Second ``generate_digest`` for the same (user, date) returns the same row.

    Mocks the LLM so the run is deterministic; counts chat calls.
    """
    user = await _make_user(db_session, email="d1@example.com")
    base = datetime(2026, 6, 29, 9, 0, tzinfo=timezone.utc)
    # Two articles so cluster_user_articles runs the LLM fast path
    # is skipped (single-article). With one article, the LLM clustering
    # call is short-circuited, so we'd only see 2 calls (clustering +
    # section + overall). Two articles exercise the full pipeline:
    # 1 clustering + 1 section + 1 overall = 3 calls.
    _make_article(db_session, user, headline="X", indexed_at=base)
    _make_article(db_session, user, headline="Y", indexed_at=base)
    await db_session.flush()

    clustering_response = json.dumps(
        [{"topic": "Topic A", "article_indices": [0, 1]}]
    )
    section_response = "Brief prose for the single cluster."
    overall_response = "Overall brief prose."

    fake = MagicMock()
    fake.chat.completions.create = AsyncMock(
        side_effect=[
            _resp(clustering_response),
            _resp(section_response),
            _resp(overall_response),
        ]
    )
    _patch_openai_client(monkeypatch, fake)

    first = await generate_digest(db_session, user.id, date(2026, 6, 29))
    second = await generate_digest(db_session, user.id, date(2026, 6, 29))

    assert first.id == second.id
    # The second call is fully idem — LLM should NOT have been re-invoked.
    # (clustering + 1 per-section + 1 overall = 3 calls on the first pass,
    # 0 calls on the second pass.)
    assert fake.chat.completions.create.await_count == 3


@pytest.mark.asyncio
async def test_generate_digest_records_notification(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful generation mints one ``Notification`` row, kind=brief_ready."""
    user = await _make_user(db_session, email="d2@example.com")
    base = datetime(2026, 6, 29, 9, 0, tzinfo=timezone.utc)
    _make_article(db_session, user, headline="A", indexed_at=base)
    await db_session.flush()

    clustering_response = json.dumps([{"topic": "X", "article_indices": [0]}])
    section_response = "Section prose."
    overall_response = "Overall prose."

    fake = MagicMock()
    fake.chat.completions.create = AsyncMock(
        side_effect=[
            _resp(clustering_response),
            _resp(section_response),
            _resp(overall_response),
        ]
    )
    _patch_openai_client(monkeypatch, fake)

    row = await generate_digest(db_session, user.id, date(2026, 6, 29))

    res = await db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    )
    notifs = list(res.scalars().all())
    assert len(notifs) == 1
    assert notifs[0].kind == "brief_ready"
    assert notifs[0].digest_id == row.id


@pytest.mark.asyncio
async def test_generate_digest_tenant_isolation(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User A's digest row is invisible to user B at the SQL layer.

    The router test (``test_notifications.py`` and the digest router
    404 path) covers the HTTP boundary. This test catches any
    service-layer leak before it hits the network.
    """
    a = await _make_user(db_session, email="d3a@example.com")
    b = await _make_user(db_session, email="d3b@example.com")
    base = datetime(2026, 6, 29, 9, 0, tzinfo=timezone.utc)
    _make_article(db_session, a, headline="A", indexed_at=base)
    await db_session.flush()

    clustering_response = json.dumps([{"topic": "X", "article_indices": [0]}])
    fake = MagicMock()
    fake.chat.completions.create = AsyncMock(
        side_effect=[
            _resp(clustering_response),
            _resp("section prose"),
            _resp("overall prose"),
        ]
    )
    _patch_openai_client(monkeypatch, fake)

    row_for_a = await generate_digest(db_session, a.id, date(2026, 6, 29))
    res = await db_session.execute(
        select(Digest).where(
            Digest.user_id == b.id,
            Digest.for_date == date(2026, 6, 29),
        )
    )
    assert res.scalar_one_or_none() is None
    assert row_for_a.user_id == a.id  # and is bound to user A, not B


# ---------------------------------------------------------------------------
# Smoke: ClusterResult dataclass shape (no DB / no LLM).
# ---------------------------------------------------------------------------


def test_cluster_result_dataclass_carries_rank_and_ids() -> None:
    """Sanity check on the dataclass — catches accidental signature drift."""
    ids = [uuid4(), uuid4()]
    c = ClusterResult(cluster_id="ai", topic="AI", article_ids=ids, rank=1)
    assert c.rank == 1
    assert c.article_ids == ids
