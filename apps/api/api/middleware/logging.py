"""Structured JSON logging + request-ID propagation middleware.

Per ADR-009 (``.agent/adr/009-json-logging.md``):

* ``JSONFormatter`` emits one single-line JSON record per call to stdout
  (§9.1). Required fields: ``timestamp``, ``level``, ``logger``,
  ``message``, ``request_id``. The ``request_id`` is injected by
  ``RequestIDFilter``, NOT by the formatter itself — the formatter only
  reads ``record.request_id`` after the filter has populated it.
* ``RequestIDFilter`` reads the active ``request_id`` from a
  ``contextvars.ContextVar`` and attaches it to every ``LogRecord``
  before the formatter runs (§9.2). This is what lets service-layer
  loggers (``logger.getLogger(__name__)`` in every router/service) pick
  up correlation without manual threading.
* ``RequestIDMiddleware`` generates or propagates the ``X-Request-ID``
  header, times the request, and emits one ``api.access`` log per
  request completion (§9.1 + §9.2).

PII / security posture (§9.3) — DO NOT add code that logs:

* ``Authorization`` headers, JWT tokens, API keys, passwords
* Cookie or ``Set-Cookie`` values
* Raw request or response bodies
* URLs that include query strings (``request.url.query`` carries
  search params, tokens, emails, PII). Log ``request.url.path`` only.

Reviewers should reject any PR that violates this list.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Context variable — populated by RequestIDMiddleware for the duration of a
# single HTTP request. Read by RequestIDFilter on every log record. Default
# is empty string so loggers called outside any request (e.g. startup hooks)
# emit ``"request_id": ""`` rather than crashing.
# ---------------------------------------------------------------------------
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the current request's ID, or ``""`` if not in a request."""
    return _request_id_var.get()


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

# Fields on the stdlib ``LogRecord`` that are infrastructure, not user data.
# Anything in this set is dropped from the JSON payload — keeping the
# emitted schema stable and predictable for downstream aggregators.
_LOGRECORD_RESERVED = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log call (§9.1).

    Required fields on every record:

    * ``timestamp`` — ISO 8601 UTC, ``Z`` suffix, millisecond precision
    * ``level`` — uppercase (``INFO``, ``WARNING``, ``ERROR``)
    * ``logger`` — ``LogRecord.name``
    * ``message`` — ``LogRecord.getMessage()`` after ``%``-formatting
    * ``request_id`` — populated upstream by ``RequestIDFilter``

    When ``exc_info`` is set on the record (e.g. ``logger.warning(...,
    exc_info=True)``), a single ``exc_info`` string field carries the
    formatted traceback — stdlib does the formatting; we just serialize it.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": (
                datetime.fromtimestamp(record.created, tz=timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Surface any ``extra={...}`` fields the caller passed. We skip
        # stdlib ``LogRecord`` internals so the schema is stable.
        for key, value in record.__dict__.items():
            if key in payload or key in _LOGRECORD_RESERVED:
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Request-ID filter
# ---------------------------------------------------------------------------


class RequestIDFilter(logging.Filter):
    """Attach ``record.request_id`` from the active ``ContextVar`` (§9.2).

    Installed on every handler that the root logger owns. Runs before the
    formatter, so the formatter can read ``record.request_id`` without
    touching the contextvar itself.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------

# Per ADR-009 §9.2: inbound IDs are accepted only if they match
# ``^[A-Za-z0-9._\-]{1,64}$``. Anything else — malformed, empty, or
# longer than 64 chars — falls back to a fresh ``uuid.uuid4().hex``.
_VALID_INBOUND_ID = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate / propagate ``X-Request-ID`` and emit access log (§9.1, §9.2).

    Behaviour:

    * If the request carries an ``X-Request-ID`` header that matches
      ``^[A-Za-z0-9._\-]{1,64}$``, adopt it as-is.
    * Otherwise (missing, malformed, or > 64 chars) mint a fresh
      ``uuid.uuid4().hex`` (32-char lowercase hex).
    * Stash the chosen ID in ``_request_id_var`` for the duration of the
      request so service-layer loggers pick it up via ``RequestIDFilter``.
    * Time the request and emit one ``api.access`` log on completion
      with ``path``, ``method``, ``status``, ``duration_ms``.
    * Echo the chosen ID back on the response as ``X-Request-ID`` so
      clients can correlate failures without parsing the body.

    The request is never rejected over a bad header.
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        inbound = request.headers.get(self.HEADER_NAME, "")
        if inbound and _VALID_INBOUND_ID.match(inbound):
            request_id = inbound
        else:
            request_id = uuid.uuid4().hex
        token = _request_id_var.set(request_id)
        try:
            request.state.request_id = request_id
            start = time.perf_counter()
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000.0, 1)
            response.headers[self.HEADER_NAME] = request_id
            # Per §9.3: log ``path`` only, never ``url`` (which carries
            # the query string and any tokens / PII it contains).
            logging.getLogger("api.access").info(
                "request completed",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            _request_id_var.reset(token)


# ---------------------------------------------------------------------------
# Root-logger setup — invoked from the FastAPI lifespan startup hook
# (see apps/api/api/main.py). Called once per process.
# ---------------------------------------------------------------------------

_CONFIGURED = False


def configure_logging(level: str) -> None:
    """Install ``JSONFormatter`` + ``RequestIDFilter`` on the root logger.

    Idempotent: a second call is a no-op so re-entering the lifespan
    context in tests does not duplicate handlers. Handlers attached by
    any earlier ``logging.basicConfig`` are detached first so records do
    not get emitted twice (one human-readable, one JSON) — this is the
    hand-off called out in ADR-009 §9.5.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"invalid log level: {level!r}")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RequestIDFilter())

    root = logging.getLogger()
    # Drop any handlers attached by an earlier basicConfig so we don't
    # double-emit (text + JSON) — per ADR-009 §9.5.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(numeric_level)

    _CONFIGURED = True


def reset_logging_for_tests() -> None:
    """Test helper: undo ``configure_logging`` so each test starts clean.

    Not part of the production API; tests import it directly.
    """
    global _CONFIGURED
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.setLevel(logging.WARNING)
    _CONFIGURED = False
