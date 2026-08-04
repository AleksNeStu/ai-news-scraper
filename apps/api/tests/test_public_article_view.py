"""Tests for the public shareable-link read endpoint (Task #33 / ADR-021).

Coverage (focused on ``GET /s/{token}`` — unauthenticated surface):

* Happy path — payload field set EXACTLY matches the
  ``SharedArticleView`` allow-list (no leaked columns).
* Unknown token → 404 ``share_not_found`` (ADR-021 §21.7).
* Expired token → 410 ``share_expired`` (ADR-021 §21.7).
* Response headers — ``Cache-Control: private, max-age=0`` AND
  ``X-Robots-Tag: noindex`` (ADR-021 §21.4).
* ``topics`` are deduped and sorted byte-stably.
* Visit-counter race-free — ``asyncio.gather`` × N=10 hits the same
  token in one second; the live count collapses to ONE row, exactly
  the de-dupe property from ADR-021 §21.6.

This file is split from :mod:`apps.api.tests.test_share` because it
focuses on the unauthenticated surface (which the Devil will review
for threat-model compliance).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from sqlalchemy import select, text

from api.db.database import AsyncSessionLocal
from api.models.shared_link import SharedLink
from api.services.shared_links import _hash_token

from .test_share import _make_article, _register_user

# The exact allow-list from ADR-021 §21.3 — used by both the allow-list
# test AND any future regression to assert no new column leaks.
EXPECTED_VIEW_KEYS: frozenset[str] = frozenset(
    {
        "article_id",
        "title",
        "summary",
        "topics",
        "source_url",
        "published_at",
        "shared_at",
        "expires_at",
    }
)


@pytest.mark.asyncio
async def test_get_shared_article_happy_path(client: AsyncClient) -> None:
    """Mint + resolve → 200, payload EXACTLY matches the allow-list."""
    user = await _register_user(client, "public-happy@example.com")
    article_id = await _make_article(
        user["user_id"],
        headline="Public Headline",
        summary="Public summary.",
        topics=["beta", "alpha", "beta"],  # duplicate to test dedupe
        source_domain="example.test",
    )

    mint = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    token = mint.json()["token"]

    resp = await client.get(f"/s/{token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Allow-list enforcement (ADR-021 §21.3).
    assert set(body.keys()) == EXPECTED_VIEW_KEYS

    # Field values.
    assert body["article_id"] == article_id
    assert body["title"] == "Public Headline"
    assert body["summary"] == "Public summary."
    # topics deduped + sorted (byte-stable).
    assert body["topics"] == ["alpha", "beta"]
    assert body["source_url"] == "https://example.test/article"
    # shared_at + expires_at are ISO 8601 strings.
    assert isinstance(body["shared_at"], str)
    assert isinstance(body["expires_at"], str)


@pytest.mark.asyncio
async def test_get_shared_article_unknown_token_returns_404(
    client: AsyncClient,
) -> None:
    """A token that hashes to nothing → 404 ``share_not_found``."""
    resp = await client.get("/s/" + "a" * 43)
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["error_code"] == "share_not_found"


@pytest.mark.asyncio
async def test_get_shared_article_expired_returns_410(
    client: AsyncClient,
) -> None:
    """A token whose row has ``expires_at`` in the past → 410 ``share_expired``."""
    user = await _register_user(client, "public-expired@example.com")
    article_id = await _make_article(user["user_id"])

    mint = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    token = mint.json()["token"]

    # Force the row's expires_at into the past via a direct UPDATE.
    # This is the only way to simulate expiry without waiting days —
    # the mint endpoint enforces ``ttl_days >= 1``.
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "UPDATE shared_links SET expires_at = :past "
                "WHERE token_hash = :token_hash"
            ),
            {
                "past": datetime.now(timezone.utc) - timedelta(seconds=1),
                "token_hash": _hash_token(token),
            },
        )
        await session.commit()

    resp = await client.get(f"/s/{token}")
    assert resp.status_code == 410, resp.text
    body = resp.json()
    assert body["error_code"] == "share_expired"


@pytest.mark.asyncio
async def test_get_shared_article_response_headers(
    client: AsyncClient,
) -> None:
    """Cache headers + robots tag set on every response (ADR-021 §21.4)."""
    user = await _register_user(client, "public-headers@example.com")
    article_id = await _make_article(user["user_id"])

    mint = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    token = mint.json()["token"]

    resp = await client.get(f"/s/{token}")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "private, max-age=0"
    assert resp.headers["X-Robots-Tag"] == "noindex"


@pytest.mark.asyncio
async def test_get_shared_article_does_not_leak_body_or_owner(
    client: AsyncClient,
) -> None:
    """Negative regression: ensure excluded columns stay excluded.

    The ``Article`` model has ``body``, ``source_domain``, ``user_id``,
    ``score``, ``tier``, ``scored_at`` — none of those may appear in
    the public response (ADR-021 §21.3 EXCLUDED table).
    """
    user = await _register_user(client, "public-noleak@example.com")
    article_id = await _make_article(
        user["user_id"],
        headline="No-leak headline",
        body="This body MUST NOT leak to anonymous visitors.",
        summary="OK to leak this summary.",
    )

    mint = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    token = mint.json()["token"]

    resp = await client.get(f"/s/{token}")
    body = resp.json()
    body_str = str(body)
    for forbidden in ("body", "source_domain", "user_id", "score", "tier", "scored_at"):
        assert forbidden not in body_str, (
            f"forbidden key {forbidden!r} leaked into public response: {body}"
        )
    # The full body text must not appear either.
    assert "MUST NOT leak" not in body_str


@pytest.mark.asyncio
async def test_visit_counter_collapse_under_concurrent_gets(
    client: AsyncClient,
) -> None:
    """N concurrent GETs in the same second → exactly 1 audit row.

    Race test for ADR-021 §21.6. The bucket-unique constraint + ON
    CONFLICT DO NOTHING MUST collapse simultaneous visits from the
    same second; the live count is the index scan after the insert.
    """
    user = await _register_user(client, "public-race@example.com")
    article_id = await _make_article(user["user_id"])

    mint = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    token = mint.json()["token"]

    # Fire 10 GETs in parallel — they should all 200 because the
    # ``ON CONFLICT DO NOTHING`` insert is idempotent under replay.
    responses = await asyncio.gather(*(client.get(f"/s/{token}") for _ in range(10)))
    for r in responses:
        assert r.status_code == 200, r.text

    # And the live audit log collapsed to one row.
    async with AsyncSessionLocal() as session:
        count = await session.scalar(
            text(
                "SELECT COUNT(*) FROM shared_link_visits v "
                "JOIN shared_links s ON s.id = v.shared_link_id "
                "WHERE s.token_hash = :token_hash"
            ),
            {"token_hash": _hash_token(token)},
        )
        assert int(count) == 1, (
            f"expected 1 audit row after 10 concurrent GETs, got {count}"
        )


@pytest.mark.asyncio
async def test_visit_counter_grows_across_seconds(
    client: AsyncClient,
) -> None:
    """Sequential GETs from different buckets count as distinct visits.

    We can't actually wait seconds in a unit test, so we instead
    insert an audit row in the past and verify the count moves by 1
    on the next GET.
    """
    user = await _register_user(client, "public-multibucket@example.com")
    article_id = await _make_article(user["user_id"])

    mint = await client.post(
        "/share",
        headers=user["headers"],
        json={"article_id": article_id},
    )
    token = mint.json()["token"]
    shared_link = await _first_shared_link(_hash_token(token))

    # Seed an audit row in a past bucket so the next GET cannot
    # collide with it.
    async with AsyncSessionLocal() as session:
        past = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=60)
        await session.execute(
            text(
                "INSERT INTO shared_link_visits "
                "(shared_link_id, visited_at, visited_at_bucket) "
                "VALUES (:sid, :past, :past) "
                "ON CONFLICT DO NOTHING"
            ),
            {"sid": str(shared_link.id), "past": past},
        )
        await session.commit()

    # Hit the token once — the new bucket is now (~0s ago).
    resp = await client.get(f"/s/{token}")
    assert resp.status_code == 200

    async with AsyncSessionLocal() as session:
        count = await session.scalar(
            text("SELECT COUNT(*) FROM shared_link_visits WHERE shared_link_id = :sid"),
            {"sid": str(shared_link.id)},
        )
        assert int(count) == 2


async def _first_shared_link(token_hash: str) -> SharedLink:
    """Test helper: fetch the first ``SharedLink`` row for ``token_hash``."""
    async with AsyncSessionLocal() as session:
        row = await session.scalar(
            select(SharedLink).where(SharedLink.token_hash == token_hash)
        )
        assert row is not None
        return row


# ---------------------------------------------------------------------------
# Rate limit (Task #65 — Devil F2 follow-up from Task #33)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_shared_article_rate_limited_returns_429(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the share_public IP-bucket is full, GET /s/{token} returns
    429 with a Retry-After header. Mirrors the test_auth.py 429
    pattern: stub the module-level ``_enforce`` to always raise.
    """
    from api.middleware import rate_limit as rate_limit_module

    async def _always_429(spec: object) -> None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    monkeypatch.setattr(rate_limit_module, "_enforce", _always_429)

    resp = await client.get("/s/anything-43-chars-of-urlsafe-base64-aaaa")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "60"
