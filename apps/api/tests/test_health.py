"""Readiness endpoint: per-check dependency status (ADR-008).

The endpoint reports 200 when Postgres + ChromaDB are both reachable
and 503 when either is down. Per-check strings identify which
dependency failed. Stack traces and messages never appear in the
response body.

These tests mock the per-check helpers so they run without a live
Postgres or Chroma server.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.routers import health as health_module


@pytest_asyncio.fixture
async def health_client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """Lifespan-aware httpx client with mocked Postgres + Chroma checks.

    Patches the module-level helpers so the endpoint never touches a
    real DB or Chroma server. Each test overrides the patches via
    ``monkeypatch.setattr`` on the same module attributes.
    """
    # Defaults: both checks report ok. Individual tests can override
    # either before issuing the request.
    monkeypatch.setattr(
        health_module,
        "_check_postgres",
        AsyncMock(return_value=("ok", None)),
    )
    monkeypatch.setattr(
        health_module,
        "_check_chroma",
        AsyncMock(return_value=("ok", None)),
    )

    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_health_happy_path_returns_200(health_client: AsyncClient) -> None:
    """When both dependencies are up: 200 + ``status: ok`` + both checks ok."""
    resp = await health_client.get("/health")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"postgres": "ok", "chroma": "ok"}


@pytest.mark.asyncio
async def test_health_postgres_down_returns_503(
    health_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Postgres check failing flips the endpoint to 503 ``degraded``."""
    monkeypatch.setattr(
        health_module,
        "_check_postgres",
        AsyncMock(return_value=("error", "error: ConnectionRefusedError")),
    )
    resp = await health_client.get("/health")
    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["postgres"].startswith("error:")
    assert body["checks"]["postgres"] == "error: ConnectionRefusedError"
    # Chroma is fine, so its check should still report ok.
    assert body["checks"]["chroma"] == "ok"


@pytest.mark.asyncio
async def test_health_chroma_down_returns_503(
    health_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chroma check failing flips the endpoint to 503 ``degraded``."""
    monkeypatch.setattr(
        health_module,
        "_check_chroma",
        AsyncMock(return_value=("error", "error: TimeoutError")),
    )
    resp = await health_client.get("/health")
    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["chroma"].startswith("error:")
    assert body["checks"]["chroma"] == "error: TimeoutError"
    # Postgres is fine, so its check should still report ok.
    assert body["checks"]["postgres"] == "ok"


@pytest.mark.asyncio
async def test_health_both_down_returns_503_with_both_errors(
    health_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both checks failing: 503 and both per-check strings carry ``error:``."""
    monkeypatch.setattr(
        health_module,
        "_check_postgres",
        AsyncMock(return_value=("error", "error: OperationalError")),
    )
    monkeypatch.setattr(
        health_module,
        "_check_chroma",
        AsyncMock(return_value=("error", "error: ConnectionRefusedError")),
    )
    resp = await health_client.get("/health")
    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["postgres"] == "error: OperationalError"
    assert body["checks"]["chroma"] == "error: ConnectionRefusedError"


@pytest.mark.asyncio
async def test_health_endpoint_does_not_leak_exception_messages(
    health_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Response body must contain only ``error: <ClassName>`` — no messages.

    The real ``_format_error`` produces ``error: <ClassName>`` and the
    real check functions feed it the caught exception. We verify that
    here by patching one check to call the real formatter and
    confirming the body never carries the original message text.
    """
    sentinel_message = (
        "host=db.internal.example.com port=5432 user=admin password=hunter2"
    )

    async def fake_pg_check() -> tuple[str, str | None]:
        try:
            raise ConnectionRefusedError(sentinel_message)
        except ConnectionRefusedError as e:
            return ("error", health_module._format_error(e))

    monkeypatch.setattr(health_module, "_check_postgres", fake_pg_check)

    resp = await health_client.get("/health")
    assert resp.status_code == 503
    body_text = resp.text
    # Class name is fine; the secret-laden message must not appear.
    assert "error: ConnectionRefusedError" in body_text
    assert sentinel_message not in body_text
    assert "hunter2" not in body_text
    assert "db.internal.example.com" not in body_text
