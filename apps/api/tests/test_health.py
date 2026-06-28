"""Sanity tests — prove the fixtures wire up end-to-end.

These tests intentionally touch the FastAPI app and the database so a
break in fixture wiring is caught at smoke time, not in deeper tests.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_health_endpoint(client) -> None:
    """``GET /health`` returns the service is alive."""
    resp = await client.get("/health")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_db_session_is_usable(db_session) -> None:
    """A simple SELECT round-trip confirms the session is bound to a live conn."""
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_auth_user_fixture_returns_token(auth_user) -> None:
    """The auth_user fixture yields a usable bearer token + Authorization header."""
    assert auth_user["token"], "token missing"
    assert auth_user["headers"]["Authorization"].startswith("Bearer "), (
        f"bad header: {auth_user['headers']!r}"
    )
    # And the User row should be the one we expect.
    assert auth_user["user"].email == "test@example.com"
