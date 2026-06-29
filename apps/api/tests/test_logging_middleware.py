"""Unit tests for the structured JSON logging + request-ID middleware.

Per ADR-009 (``.agent/adr/009-json-logging.md``). Each test exercises
one of the sub-decisions:

* §9.1 — JSON record shape, exc_info serialization, access log fields
* §9.2 — request-ID generation, inbound adoption, inbound rejection
* §9.3 — PII posture (asserted implicitly: ``url.path`` only, no
  ``Authorization`` log path)

The ``client`` fixture from ``conftest.py`` drives the FastAPI lifespan
so ``configure_logging`` runs once per test. We call
``reset_logging_for_tests`` from the middleware module around each
``caplog`` assertion so the caplog handler we install is the only thing
in the handler chain.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from api.middleware import logging as logging_module
from api.middleware.logging import (
    JSONFormatter,
    RequestIDFilter,
    RequestIDMiddleware,
    configure_logging,
    get_request_id,
    reset_logging_for_tests,
)
from api.routers import health as health_module


# ---------------------------------------------------------------------------
# JSONFormatter — §9.1
# ---------------------------------------------------------------------------


def _make_record(
    name: str = "api.test",
    level: int = logging.INFO,
    msg: str = "hello",
    args: tuple[Any, ...] = (),
    exc_info=None,
    extra: dict[str, Any] | None = None,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=10,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )
    if extra:
        for key, value in extra.items():
            setattr(record, key, value)
    return record


def test_json_formatter_emits_required_fields() -> None:
    """Every record carries timestamp, level, logger, message, request_id."""
    formatter = JSONFormatter()
    record = _make_record(msg="hello %s", args=("world",), extra={"request_id": "abc"})
    rendered = formatter.format(record)
    parsed = json.loads(rendered)

    assert parsed["timestamp"].endswith("Z"), parsed["timestamp"]
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", parsed["timestamp"]
    )
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "api.test"
    assert parsed["message"] == "hello world"  # %-formatting applied
    assert parsed["request_id"] == "abc"


def test_json_formatter_handles_exc_info() -> None:
    """``exc_info=True`` records carry a stringified traceback under ``exc_info``."""
    formatter = JSONFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record(
            level=logging.WARNING,
            msg="failed",
            exc_info=sys.exc_info(),
        )
    rendered = formatter.format(record)
    parsed = json.loads(rendered)

    assert "exc_info" in parsed, rendered
    assert isinstance(parsed["exc_info"], str)
    assert "ValueError: boom" in parsed["exc_info"]
    assert "Traceback" in parsed["exc_info"]


def test_json_formatter_includes_extra_fields() -> None:
    """Custom ``extra={...}`` fields surface in the JSON payload."""
    formatter = JSONFormatter()
    record = _make_record(
        msg="ctx",
        extra={"article_id": 42, "request_id": "r"},
    )
    parsed = json.loads(formatter.format(record))
    assert parsed["article_id"] == 42
    assert parsed["request_id"] == "r"


def test_json_formatter_omits_stdlib_logrecord_internals() -> None:
    """Path/lineno/process/thread never leak into the JSON payload."""
    formatter = JSONFormatter()
    record = _make_record(msg="x")
    parsed = json.loads(formatter.format(record))
    for reserved in {
        "pathname",
        "lineno",
        "process",
        "thread",
        "msecs",
        "args",
        "msg",
        "levelno",
        "funcName",
    }:
        assert reserved not in parsed, f"unexpected stdlib field leaked: {reserved}"


# ---------------------------------------------------------------------------
# RequestIDFilter — §9.2 (filter injects contextvar into every record)
# ---------------------------------------------------------------------------


def test_request_id_filter_injects_contextvar(monkeypatch: pytest.MonkeyPatch) -> None:
    """A record that flows through the filter carries ``request_id`` from the contextvar."""
    token = logging_module._request_id_var.set("from-ctx")
    try:
        record = logging.LogRecord(
            name="x",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="m",
            args=(),
            exc_info=None,
        )
        RequestIDFilter().filter(record)
        assert record.request_id == "from-ctx"  # type: ignore[attr-defined]
    finally:
        logging_module._request_id_var.reset(token)


# ---------------------------------------------------------------------------
# RequestIDMiddleware — §9.2 (header behaviour)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_generates_uuidv4_when_no_header(client: AsyncClient) -> None:
    """No inbound header → response carries a fresh 32-char lowercase hex."""
    resp = await client.get("/health")
    request_id = resp.headers.get("X-Request-ID", "")
    assert re.match(r"^[0-9a-f]{32}$", request_id), request_id


@pytest.mark.asyncio
async def test_middleware_honors_valid_inbound_header(client: AsyncClient) -> None:
    """Inbound header matching ``^[A-Za-z0-9._\\-]{1,64}$`` is echoed back verbatim."""
    resp = await client.get("/health", headers={"X-Request-ID": "my-test-id"})
    assert resp.headers.get("X-Request-ID") == "my-test-id"


@pytest.mark.asyncio
async def test_middleware_rejects_oversized_inbound_header(client: AsyncClient) -> None:
    """Inbound header > 64 chars is rejected in favor of a fresh UUIDv4 hex."""
    oversized = "a" * 100
    resp = await client.get("/health", headers={"X-Request-ID": oversized})
    request_id = resp.headers.get("X-Request-ID", "")
    assert request_id != oversized
    assert re.match(r"^[0-9a-f]{32}$", request_id), request_id


@pytest.mark.asyncio
async def test_middleware_rejects_malformed_inbound_header(client: AsyncClient) -> None:
    """Inbound header with disallowed characters is rejected (fallback UUIDv4)."""
    # Slashes are outside the ``[A-Za-z0-9._\\-]`` allow-list.
    resp = await client.get("/health", headers={"X-Request-ID": "bad/id with spaces"})
    request_id = resp.headers.get("X-Request-ID", "")
    assert re.match(r"^[0-9a-f]{32}$", request_id), request_id


# ---------------------------------------------------------------------------
# Access log — §9.1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_emits_access_log_with_required_fields(
    client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each completed request emits exactly one ``api.access`` log with all 4 fields."""
    # Mock health checks so the /health endpoint returns 200 without
    # needing a live Postgres/Chroma. Same pattern as test_health.py.
    monkeypatch.setattr(
        health_module, "_check_postgres", AsyncMock(return_value=("ok", None))
    )
    monkeypatch.setattr(
        health_module, "_check_chroma", AsyncMock(return_value=("ok", None))
    )
    # Note: do NOT call reset_logging_for_tests() here — it removes
    # caplog's root handler along with the JSON handler, so caplog
    # cannot capture records for assertions below.
    caplog.set_level(logging.INFO, logger="api.access")
    resp = await client.get("/health")
    assert resp.status_code == 200

    access_records = [r for r in caplog.records if r.name == "api.access"]
    assert len(access_records) == 1, [r.name for r in caplog.records]
    record = access_records[0]
    assert record.message == "request completed"
    assert record.path == "/health"  # type: ignore[attr-defined]
    assert record.method == "GET"  # type: ignore[attr-defined]
    assert record.status == 200  # type: ignore[attr-defined]
    assert isinstance(record.duration_ms, float)  # type: ignore[attr-defined]
    assert record.duration_ms >= 0.0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_access_log_carries_request_id_for_correlation(
    client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The access-log record carries the same ``request_id`` as the response header."""
    # Mock health checks so /health returns 200 offline. Same pattern as test_health.py.
    monkeypatch.setattr(
        health_module, "_check_postgres", AsyncMock(return_value=("ok", None))
    )
    monkeypatch.setattr(
        health_module, "_check_chroma", AsyncMock(return_value=("ok", None))
    )
    # Do NOT call reset_logging_for_tests() here either — see comment above.
    caplog.set_level(logging.INFO, logger="api.access")
    resp = await client.get("/health", headers={"X-Request-ID": "trace-123"})
    header_id = resp.headers["X-Request-ID"]
    assert header_id == "trace-123"

    access_records = [r for r in caplog.records if r.name == "api.access"]
    assert len(access_records) == 1
    assert getattr(access_records[0], "request_id", "") == "trace-123"


# ---------------------------------------------------------------------------
# get_request_id — outside a request context
# ---------------------------------------------------------------------------


def test_get_request_id_is_empty_outside_request_context() -> None:
    """Outside any request, ``get_request_id()`` returns ``""`` rather than crashing."""
    # The fixture / module imports may have set the var; clear explicitly
    # so this test is independent of import order.
    logging_module._request_id_var.set("")
    assert get_request_id() == ""


# ---------------------------------------------------------------------------
# configure_logging — idempotency + level validation
# ---------------------------------------------------------------------------


def test_configure_logging_is_idempotent() -> None:
    """Calling ``configure_logging`` twice does not double the handler count."""
    reset_logging_for_tests()
    configure_logging("INFO")
    handlers_after_first = list(logging.getLogger().handlers)
    configure_logging("INFO")
    handlers_after_second = list(logging.getLogger().handlers)
    assert len(handlers_after_first) == len(handlers_after_second) == 1
    reset_logging_for_tests()


def test_configure_logging_rejects_invalid_level() -> None:
    """An invalid level string raises at config time, not on first log."""
    reset_logging_for_tests()
    with pytest.raises(ValueError, match="invalid log level"):
        configure_logging("BANANA")
    reset_logging_for_tests()


def test_request_id_middleware_class_is_exported() -> None:
    """Smoke: the public API the prompt requires is importable."""
    # If any of these renames, the import at the top of this module would
    # already have failed — but the explicit assertion makes the intent
    # obvious to a reader.
    assert RequestIDMiddleware is not None
    assert JSONFormatter is not None
    assert RequestIDFilter is not None
