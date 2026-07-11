"""Tests for ``POST /feeds/bulk`` (Task #35 / ADR-024).

Bulk-import of RSS feeds via OPML. The endpoint accepts up to 500 feed
references and returns partial-success semantics: HTTP 200 with
``{created, skipped_duplicates, failed[]}`` regardless of per-item
failures.

Coverage (per the brief):

  * Happy path — three fresh URLs, parse OK → ``created=3``.
  * Existing-feed dedup — pre-inserted URLs are skipped, not duplicated.
  * Partial parse failure — mix of OK and None-returning parses →
    ``failed[]`` carries the URL + reason.
  * Validation — empty ``feeds`` → 422 (Pydantic ``min_length=1``);
    501 items → 422 (``max_length=500``).
  * Intra-request dedup — same URL twice in one body →
    ``created=1, failed=[{url, "Duplicate URL in same request"}]``.
  * Per-user isolation — two users bulk-importing the same URLs each
    get ``created=3`` (UNIQUE constraint is per-user).
  * Unauthenticated — no auth → 401.

Mock strategy: ``FeedParser`` is patched so tests don't hit the
network. The fixture ``mock_parser`` maps each URL to ``ParsedFeed``
(success) or ``None`` (parse failure).

Rate-limit note: every test calls ``POST /auth/register`` to mint a
real user — 8+ registrations per file would exceed the per-IP 5/3600
limit on a Redis-backed dev stack. An autouse fixture monkey-patches
``rate_limit._enforce`` to a no-op so each test starts with a clean
bucket. CI ships without Redis (the limit fails open there already);
this fixture only matters for ``make test-api``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from api.db.database import AsyncSessionLocal
from api.models.feed import Feed
from api.services.feed_parser import ParsedFeed, ParsedFeedItem


# ---------------------------------------------------------------------------
# Autouse — neutralise the per-IP register rate limit so 8+ tests
# don't trip the 5/3600 bucket on a Redis-backed ``make test-api``
# run. CI has no Redis, so this is a no-op there.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _disable_register_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub ``rate_limit._enforce`` to a no-op for the duration of
    each test. ``rate_limit_ip("register", ...)`` builds a closure
    that calls this primitive; replacing the primitive neutralises
    every consumer at once.
    """
    from api.middleware import rate_limit as rate_limit_module

    async def _no_enforce(spec: object) -> None:
        return None

    monkeypatch.setattr(rate_limit_module, "_enforce", _no_enforce)


# ---------------------------------------------------------------------------
# Helpers — local builders / mock factories
# ---------------------------------------------------------------------------


async def _register_user(client: AsyncClient, email: str) -> dict[str, Any]:
    """Register via ``POST /auth/register`` and return headers + user_id.

    Mirrors ``tests/test_share.py::_register_user``. The endpoint
    commits through ``get_db``, so the user is visible to subsequent
    requests on the same ``client`` instance — which is what we need
    for ``feeds`` FK lookups in the bulk endpoint.
    """
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": "strongpass123"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return {
        "user_id": body["user"]["id"],
        "token": body["token"],
        "headers": {"Authorization": f"Bearer {body['token']}"},
    }


async def _seed_feed(owner_id: str, url: str) -> None:
    """Insert a Feed through the production session.

    Uses ``AsyncSessionLocal`` (the production session maker) so the
    row is committed and visible to the API's ``get_db`` calls.
    """
    async with AsyncSessionLocal() as session:
        session.add(
            Feed(
                user_id=owner_id,
                feed_url=url,
                title="seeded",
                description="seeded",
            )
        )
        await session.commit()


def _ok_parse(url: str) -> ParsedFeed:
    """Default parser stub — returns a tiny but valid ParsedFeed."""
    return ParsedFeed(
        title=f"Title for {url}",
        description=f"Description for {url}",
        items=[
            ParsedFeedItem(
                guid=f"guid-{url}",
                title="item",
                url=url,
                summary=None,
                published=None,
            )
        ],
    )


@pytest.fixture
def mock_parser():
    """Patch ``api.routers.feeds.FeedParser``.

    Yields a helper ``set(url_to_outcome)`` that maps each URL to a
    ParsedFeed (success) or ``None`` (parse failure). Any URL not in
    the map gets the default success stub.
    """
    outcomes: dict[str, ParsedFeed | None] = {}

    class _Stub:
        def __init__(self) -> None:
            pass

        def parse(self, url: str) -> ParsedFeed | None:
            if url in outcomes:
                return outcomes[url]
            return _ok_parse(url)

    def set(map_: dict[str, ParsedFeed | None]) -> None:
        outcomes.clear()
        outcomes.update(map_)

    with patch("api.routers.feeds.FeedParser") as MockParser:
        MockParser.return_value = _Stub()
        yield set


# ---------------------------------------------------------------------------
# T1 — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_import_creates_new_feeds(
    client: AsyncClient, mock_parser
) -> None:
    """Three fresh URLs, all parse OK → created=3, skipped=0, failed=[]."""
    user = await _register_user(client, "bulk-happy@example.com")
    payload = {
        "feeds": [
            {"xmlUrl": "https://example.com/feed-a", "title": "A"},
            {"xmlUrl": "https://example.com/feed-b", "title": "B"},
            {"xmlUrl": "https://example.com/feed-c", "title": "C"},
        ]
    }

    resp = await client.post("/feeds/bulk", headers=user["headers"], json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["created"] == 3
    assert body["skipped_duplicates"] == 0
    assert body["failed"] == []

    # Verify the rows actually landed in the DB.
    async with AsyncSessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(Feed).where(Feed.user_id == user["user_id"])
                )
            )
            .scalars()
            .all()
        )
        urls = {r.feed_url for r in rows}
    assert urls == {
        "https://example.com/feed-a",
        "https://example.com/feed-b",
        "https://example.com/feed-c",
    }


# ---------------------------------------------------------------------------
# T2 — existing-feed dedup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_import_dedupes_existing(
    client: AsyncClient, mock_parser
) -> None:
    """Pre-insert two feeds, POST three URLs (2 existing + 1 new) →
    created=1, skipped=2, failed=[].
    """
    user = await _register_user(client, "bulk-dedup@example.com")
    # Seed two existing feeds for this user.
    await _seed_feed(user["user_id"], "https://example.com/existing-a")
    await _seed_feed(user["user_id"], "https://example.com/existing-b")

    payload = {
        "feeds": [
            {"xmlUrl": "https://example.com/existing-a", "title": "A"},
            {"xmlUrl": "https://example.com/existing-b", "title": "B"},
            {"xmlUrl": "https://example.com/fresh", "title": "Fresh"},
        ]
    }

    resp = await client.post("/feeds/bulk", headers=user["headers"], json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["created"] == 1
    assert body["skipped_duplicates"] == 2
    assert body["failed"] == []


# ---------------------------------------------------------------------------
# T3 — partial parse failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_import_partial_parse_failure(
    client: AsyncClient, mock_parser
) -> None:
    """Two OK + one returning None → created=2, failed=[{url, reason}]."""
    user = await _register_user(client, "bulk-partial@example.com")
    bad_url = "https://example.com/broken"

    def _broken(_: str) -> ParsedFeed | None:
        return None

    mock_parser(
        {
            "https://example.com/good-a": _ok_parse("https://example.com/good-a"),
            "https://example.com/good-b": _ok_parse("https://example.com/good-b"),
            bad_url: None,
        }
    )

    payload = {
        "feeds": [
            {"xmlUrl": "https://example.com/good-a", "title": "A"},
            {"xmlUrl": bad_url, "title": "Broken"},
            {"xmlUrl": "https://example.com/good-b", "title": "B"},
        ]
    }

    resp = await client.post("/feeds/bulk", headers=user["headers"], json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["created"] == 2
    assert body["skipped_duplicates"] == 0
    assert body["failed"] == [{"url": bad_url, "reason": "Could not parse feed"}]


# ---------------------------------------------------------------------------
# T4 — empty list rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_import_rejects_empty(client: AsyncClient, mock_parser) -> None:
    """``feeds=[]`` violates Pydantic ``min_length=1`` → 422."""
    user = await _register_user(client, "bulk-empty@example.com")

    resp = await client.post(
        "/feeds/bulk",
        headers=user["headers"],
        json={"feeds": []},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T5 — over-cap rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_import_rejects_too_many(
    client: AsyncClient, mock_parser
) -> None:
    """501 items violates Pydantic ``max_length=500`` → 422."""
    user = await _register_user(client, "bulk-toomany@example.com")

    payload = {
        "feeds": [
            {"xmlUrl": f"https://example.com/feed-{i}", "title": f"F{i}"}
            for i in range(501)
        ]
    }

    resp = await client.post("/feeds/bulk", headers=user["headers"], json=payload)
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T6 — intra-request dedup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_import_dedupes_intra_request(
    client: AsyncClient, mock_parser
) -> None:
    """Same URL twice in one body → created=1, failed=[{url, reason}]."""
    user = await _register_user(client, "bulk-intra@example.com")
    dup_url = "https://example.com/dup"

    payload = {
        "feeds": [
            {"xmlUrl": dup_url, "title": "First"},
            {"xmlUrl": dup_url, "title": "Second"},
        ]
    }

    resp = await client.post("/feeds/bulk", headers=user["headers"], json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["created"] == 1
    assert body["skipped_duplicates"] == 0
    assert body["failed"] == [
        {"url": dup_url, "reason": "Duplicate URL in same request"}
    ]


# ---------------------------------------------------------------------------
# T7 — per-user isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_import_isolated_per_user(
    client: AsyncClient, mock_parser
) -> None:
    """User A and user B both POST the same three URLs → each gets
    ``created=3``. The ``(user_id, feed_url)`` UNIQUE constraint is
    per-user — there is no cross-user leak.
    """
    user_a = await _register_user(client, "bulk-iso-a@example.com")
    user_b = await _register_user(client, "bulk-iso-b@example.com")

    payload = {
        "feeds": [
            {"xmlUrl": "https://example.com/shared-1", "title": "1"},
            {"xmlUrl": "https://example.com/shared-2", "title": "2"},
            {"xmlUrl": "https://example.com/shared-3", "title": "3"},
        ]
    }

    resp_a = await client.post(
        "/feeds/bulk", headers=user_a["headers"], json=payload
    )
    assert resp_a.status_code == 200, resp_a.text
    assert resp_a.json()["created"] == 3

    resp_b = await client.post(
        "/feeds/bulk", headers=user_b["headers"], json=payload
    )
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json()["created"] == 3

    # Each user owns exactly their three feeds — six rows total.
    async with AsyncSessionLocal() as session:
        rows_a = (
            (
                await session.execute(
                    select(Feed).where(Feed.user_id == user_a["user_id"])
                )
            )
            .scalars()
            .all()
        )
        rows_b = (
            (
                await session.execute(
                    select(Feed).where(Feed.user_id == user_b["user_id"])
                )
            )
            .scalars()
            .all()
        )
    assert len(rows_a) == 3
    assert len(rows_b) == 3
    assert {r.feed_url for r in rows_a} == {r.feed_url for r in rows_b}


# ---------------------------------------------------------------------------
# T8 — unauthenticated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_import_unauthenticated(
    client: AsyncClient, mock_parser
) -> None:
    """No Authorization header / cookie → 401."""
    resp = await client.post(
        "/feeds/bulk",
        json={
            "feeds": [
                {"xmlUrl": "https://example.com/feed", "title": "X"},
            ]
        },
    )
    assert resp.status_code == 401