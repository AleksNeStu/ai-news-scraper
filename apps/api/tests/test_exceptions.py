"""Unit tests for the RFC 7807 problem+json exception handlers.

Per ADR-010 (``.agent/adr/010-exception-hierarchy.md``). The ``client``
fixture from ``conftest.py`` drives the FastAPI lifespan so the global
exception handlers are registered exactly once for the test session.

Each test mounts a temporary route that raises one of the documented
exception types, then asserts the response shape (status, body, headers)
conforms to ADR-010 §10.2 + §10.3.

PII posture (ADR-010 §10.5) is asserted by
``test_catch_all_500_does_not_leak_traceback`` and
``test_handler_never_returns_stacktrace_text``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from api.exceptions import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    UpstreamError,
    ValidationError,
)
from api.routers import health as health_module


# ---------------------------------------------------------------------------
# Helpers — register throw-away routes that raise each exception type.
# ---------------------------------------------------------------------------


def _mount_app_exception_route(app, path: str, exc: AppException) -> None:
    """Register a one-shot GET route on ``app`` that raises ``exc``."""

    @app.get(path)
    async def _boom():
        raise exc


def _mount_http_exception_route(app, path: str, exc: HTTPException) -> None:
    @app.get(path)
    async def _boom():
        raise exc


def _mount_catch_all_route(app, path: str, exc: Exception) -> None:
    @app.get(path)
    async def _boom():
        raise exc


def _register_routes(app) -> None:
    """Attach one throw-away route per exception type to ``app``.

    Done once per test session — the ``client`` fixture yields a fresh
    AsyncClient per test, but the routes persist on the shared ``app``
    object. The paths are unique to this test module so they cannot
    collide with production routers.
    """
    _mount_app_exception_route(
        app, "/test-throw/not-found", NotFoundError("Article", id=42)
    )
    _mount_app_exception_route(
        app, "/test-throw/validation", ValidationError("Bad payload", field="email")
    )
    _mount_app_exception_route(
        app,
        "/test-throw/authentication",
        AuthenticationError("Token expired"),
    )
    _mount_app_exception_route(
        app,
        "/test-throw/authorization",
        AuthorizationError("Requires admin"),
    )
    _mount_app_exception_route(
        app,
        "/test-throw/upstream",
        UpstreamError("OpenAI 503", service="openai"),
    )
    _mount_http_exception_route(
        app,
        "/test-throw/http-compat",
        HTTPException(status_code=404, detail="Article not found"),
    )
    _mount_catch_all_route(
        app, "/test-throw/boom", RuntimeError("something internal exploded")
    )


# ---------------------------------------------------------------------------
# Required RFC 7807 fields on every response body
# ---------------------------------------------------------------------------


_REQUIRED_FIELDS = ("type", "title", "status", "detail", "instance", "error_code")


def _assert_rfc7807_shape(body: dict[str, Any], expected_status: int) -> None:
    for field in _REQUIRED_FIELDS:
        assert field in body, f"missing required field {field!r}: {body}"
    assert body["status"] == expected_status
    assert body["type"].startswith("https://ai-news-scraper/errors/")
    assert isinstance(body["instance"], str)  # X-Request-ID (or "" if no middleware)


# ---------------------------------------------------------------------------
# AppException subclasses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_not_found_error_returns_404_with_context(
    client: AsyncClient,
) -> None:
    _register_routes(client._transport.app)  # type: ignore[attr-defined]
    resp = await client.get("/test-throw/not-found")
    assert resp.status_code == 404
    body = resp.json()
    _assert_rfc7807_shape(body, 404)
    assert body["error_code"] == "not_found"
    assert body["title"] == "Resource not found"
    assert body["detail"] == "Article"
    assert body["context"] == {"id": 42}


@pytest.mark.asyncio
async def test_validation_error_returns_400(client: AsyncClient) -> None:
    _register_routes(client._transport.app)  # type: ignore[attr-defined]
    resp = await client.get("/test-throw/validation")
    assert resp.status_code == 400
    body = resp.json()
    _assert_rfc7807_shape(body, 400)
    assert body["error_code"] == "validation_error"
    assert body["context"] == {"field": "email"}


@pytest.mark.asyncio
async def test_authentication_error_returns_401(client: AsyncClient) -> None:
    _register_routes(client._transport.app)  # type: ignore[attr-defined]
    resp = await client.get("/test-throw/authentication")
    assert resp.status_code == 401
    body = resp.json()
    _assert_rfc7807_shape(body, 401)
    assert body["error_code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_authorization_error_returns_403(client: AsyncClient) -> None:
    _register_routes(client._transport.app)  # type: ignore[attr-defined]
    resp = await client.get("/test-throw/authorization")
    assert resp.status_code == 403
    body = resp.json()
    _assert_rfc7807_shape(body, 403)
    assert body["error_code"] == "forbidden"


@pytest.mark.asyncio
async def test_upstream_error_returns_502(client: AsyncClient) -> None:
    _register_routes(client._transport.app)  # type: ignore[attr-defined]
    resp = await client.get("/test-throw/upstream")
    assert resp.status_code == 502
    body = resp.json()
    _assert_rfc7807_shape(body, 502)
    assert body["error_code"] == "upstream_error"
    assert body["context"] == {"service": "openai"}


# ---------------------------------------------------------------------------
# Backward compatibility — old ``raise HTTPException(...)`` call sites
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_exception_backward_compat(client: AsyncClient) -> None:
    """Old code that raises ``fastapi.HTTPException`` still produces RFC 7807.

    Per ADR-010 §10.6: maps to problem+json with ``error_code="http_error"``;
    preserves caller-supplied headers (e.g. ``WWW-Authenticate: Bearer`` on 401).
    """
    _register_routes(client._transport.app)  # type: ignore[attr-defined]
    resp = await client.get("/test-throw/http-compat")
    assert resp.status_code == 404
    body = resp.json()
    _assert_rfc7807_shape(body, 404)
    assert body["error_code"] == "http_error"
    assert body["detail"] == "Article not found"


# ---------------------------------------------------------------------------
# Catch-all — unhandled ``Exception`` becomes a 500 with no internals leaked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catch_all_500_does_not_leak_traceback(
    client: AsyncClient,
) -> None:
    """Unhandled ``Exception`` → 500 with a generic body; traceback logged only."""
    _register_routes(client._transport.app)  # type: ignore[attr-defined]
    resp = await client.get("/test-throw/boom")
    assert resp.status_code == 500
    body = resp.json()
    _assert_rfc7807_shape(body, 500)
    assert body["error_code"] == "internal_error"
    assert "context" not in body  # no kwargs on bare Exception
    # The detail MUST be the generic safe message — never the RuntimeError message.
    assert "something internal exploded" not in body["detail"]
    assert "RuntimeError" not in body["detail"]
    assert body["detail"].startswith("An unexpected error occurred")


@pytest.mark.asyncio
async def test_handler_never_returns_stacktrace_text(
    client: AsyncClient,
) -> None:
    """Even a deeply-nested traceback must not appear in any error body."""
    _register_routes(client._transport.app)  # type: ignore[attr-defined]

    # Inject a route that raises a chained exception to ensure traceback
    # frames never leak.
    @client._transport.app.get("/test-throw/nested")  # type: ignore[attr-defined]
    async def _nested():
        try:
            raise ValueError("inner cause")
        except ValueError as inner:
            raise RuntimeError("outer wrapped") from inner

    resp = await client.get("/test-throw/nested")
    assert resp.status_code == 500
    body_text = resp.text
    for forbidden in (
        "Traceback",
        "inner cause",
        "outer wrapped",
        "ValueError",
        "RuntimeError",
        "test_exceptions.py",
        "raise ",
    ):
        assert forbidden not in body_text, f"leaked {forbidden!r} in body: {body_text}"


# ---------------------------------------------------------------------------
# Correlation — ``instance`` equals ``X-Request-ID`` from response header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instance_field_matches_request_id_header(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per ADR-009 + ADR-010: body's ``instance`` == response ``X-Request-ID``."""
    # Mock the /test-throw/health-check path so we hit a clean route.
    # We don't need a /test-throw/health route here; we just need a real
    # endpoint that returns 200, which is /health (after mocking).
    monkeypatch.setattr(
        health_module, "_check_postgres", AsyncMock(return_value=("ok", None))
    )
    monkeypatch.setattr(
        health_module, "_check_chroma", AsyncMock(return_value=("ok", None))
    )
    _register_routes(client._transport.app)  # type: ignore[attr-defined]

    resp = await client.get(
        "/test-throw/not-found",
        headers={"X-Request-ID": "correlation-test-001"},
    )
    header_id = resp.headers["X-Request-ID"]
    body = resp.json()
    assert header_id == "correlation-test-001"
    assert body["instance"] == "correlation-test-001"
