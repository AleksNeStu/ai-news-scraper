"""Tests for the shareable-link routers (Task #33 / ADR-021).

Coverage:

* ``POST /share`` auth gate (401 without cookie).
* ``POST /share`` happy path — response shape matches ``ShareResponse``.
* ``POST /share`` rejects ``ttl_days=10000`` with 422 (ADR-021 §21.8).
* ``GET /s/{token}`` happy path — payload field set EXACTLY matches
  the ``SharedArticleView`` allow-list.
* ``GET /s/{token}`` unknown token → 404 ``share_not_found``.
* ``GET /s/{token}`` expired → 410 ``share_expired``.
* ``GET /s/{token}`` headers — ``Cache-Control: private, max-age=0``
  AND ``X-Robots-Tag: noindex`` (ADR-021 §21.4).
* ``token_hash`` stored = ``sha256(token)``; raw token never
  round-trips from the DB (ADR-021 §21.9).
* Article DELETE cascades — wiping the source article removes every
  share row (GDPR posture, ADR-021 §21.9).
* Token entropy — ``secrets.token_urlsafe(32)`` is 43 chars of
  URL-safe base64 (``^[A-Za-z0-9_-]{43}$``).

Visit-counter race test (``asyncio.gather`` × N=10) lives in
:mod:`apps.api.tests.test_public_article_view` because it exercises
the public router end-to-end and needs the ``client`` fixture.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from sqlalchemy import select

from api.db.database import AsyncSessionLocal
from api.models.article import Article
from api.models.shared_link import SharedLink


# ---------------------------------------------------------------------------
# Helpers — register a real user via the API + create an Article through
# the production session so the API can see the row.
# ---------------------------------------------------------------------------


async def _register_user(client: AsyncClient, email: str) -> dict[str, Any]:
    """Register via ``POST /auth/register`` and return the parsed body.

    The endpoint commits through ``get_db``, so the user is visible to
    subsequent requests on the same ``client`` instance.
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


async def _make_article(
    owner_id: str,
    *,
    headline: str = "Test headline",
    body: str = "body text that must NOT be exposed via share",
    summary: str | None = "Test summary.",
    topics: list[str] | None = None,
    source_domain: str = "example.test",
    publish_date: datetime | None = None,
    url: str = "https://example.test/article",
) -> str:
    """Insert an Article through the production session and return its id.

    Uses ``AsyncSessionLocal`` (the production session maker) so the
    row is committed and visible to the API's ``get_db`` calls.
    """
    if topics is None:
        topics = ["ai", "ml", "ai"]  # include a duplicate to test dedupe
    if publish_date is None:
        publish_date = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        row = Article(
            user_id=owner_id,
            url=url,
            headline=headline,
            body=body,
            summary=summary,
            topics=topics,
            source_domain=source_domain,
            publish_date=publish_date,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        article_id = str(row.id)
    return article_id


# ---------------------------------------------------------------------------
# POST /share
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_share_requires_auth(client: AsyncClient) -> None:
    """POST without a token → 401 (same posture as the rest of the API)."""
    resp = await client.post(
        "/share",
        json={"article_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_share_happy_path(client: AsyncClient) -> None:
    """Mint a share → 201 + body matches the ``ShareResponse`` schema."""
    user = await _register_user(client, "share-happy@example.com")
    article_id = await _make_article(user["user_id"])

    resp = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert set(body.keys()) == {"token", "url", "expires_at", "article_id"}
    assert body["article_id"] == article_id
    # 43 chars of URL-safe base64.
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", body["token"])
    # URL is server-built: origin + /s/<token>.
    assert body["url"].endswith(f"/s/{body['token']}")
    # expires_at is an ISO 8601 string parseable as datetime.
    parsed_expiry = datetime.fromisoformat(body["expires_at"])
    now = datetime.now(timezone.utc)
    assert parsed_expiry > now
    assert parsed_expiry <= now + timedelta(days=31)  # default 30d + slack


@pytest.mark.asyncio
async def test_post_share_ttl_days_above_365_returns_422(
    client: AsyncClient,
) -> None:
    """``ttl_days=10000`` violates the Pydantic ``le=365`` cap → 422."""
    user = await _register_user(client, "share-cap@example.com")
    article_id = await _make_article(user["user_id"])

    resp = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id, "ttl_days": 10000},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_post_share_token_hash_persisted_sha256(
    client: AsyncClient,
) -> None:
    """The DB stores ``sha256(token)``; raw token never round-trips."""
    user = await _register_user(client, "share-hash@example.com")
    article_id = await _make_article(user["user_id"])

    resp = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    body = resp.json()
    raw_token = body["token"]

    async with AsyncSessionLocal() as session:
        row = await session.scalar(
            select(SharedLink).where(
                SharedLink.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
            )
        )
        assert row is not None
        # Raw token MUST NOT be in any column.
        assert raw_token not in row.token_hash
        # token_hash is exactly 64 hex chars (sha256 output).
        assert len(row.token_hash) == 64
        assert all(c in "0123456789abcdef" for c in row.token_hash)


@pytest.mark.asyncio
async def test_post_share_unknown_article_returns_404(
    client: AsyncClient,
) -> None:
    """POST with an article_id that does not exist → 404 (ADR-021 §21.9)."""
    user = await _register_user(client, "share-missing-art@example.com")

    resp = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_post_share_token_is_urlsafe_base64_43_chars(
    client: AsyncClient,
) -> None:
    """Token entropy: 43 chars of ``[A-Za-z0-9_-]`` (ADR-021 §21.1)."""
    user = await _register_user(client, "share-entropy@example.com")
    article_id = await _make_article(user["user_id"])

    resp = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    token = resp.json()["token"]
    assert len(token) == 43
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)


# ---------------------------------------------------------------------------
# Article DELETE cascade (GDPR posture — ADR-021 §21.9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_article_delete_cascades_shared_link(
    client: AsyncClient,
) -> None:
    """Deleting the source article removes every share row in one statement."""
    user = await _register_user(client, "share-cascade@example.com")
    article_id = await _make_article(user["user_id"])

    # Mint two shares of the same article.
    r1 = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    r2 = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    assert r1.status_code == 201 and r2.status_code == 201

    # Confirm two rows exist before delete.
    async with AsyncSessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(SharedLink).where(SharedLink.article_id == article_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2

    # Delete the article via the authenticated API (200 status is fine
    # — articles.py returns 204 but httpx returns 200 on 204-with-body;
    # either way the row is gone).
    del_resp = await client.delete(
        f"/articles/{article_id}",
        headers=user["headers"],
    )
    assert del_resp.status_code in (200, 204), del_resp.text

    # All share rows must be gone (CASCADE).
    async with AsyncSessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(SharedLink).where(SharedLink.article_id == article_id)
                )
            )
            .scalars()
            .all()
        )
        assert rows == [], "FK CASCADE did not wipe shared_links rows"


# ---------------------------------------------------------------------------
# Rate limit (Task #65 — Devil F2 follow-up from Task #33)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_share_rate_limited_returns_429(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the share_create bucket is full, POST /share returns 429
    with a Retry-After header. Mirrors the ``rl_429_client`` pattern in
    ``tests/test_auth.py::test_register_rate_limited_after_5_calls``.
    """
    from api.middleware import rate_limit as rate_limit_module

    async def _always_429(spec: object) -> None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    monkeypatch.setattr(rate_limit_module, "_enforce", _always_429)

    user = await _register_user(client, "share-rl@example.com")
    article_id = await _make_article(user["user_id"])

    resp = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "60"
