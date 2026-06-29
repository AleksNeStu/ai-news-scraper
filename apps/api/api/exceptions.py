"""API exception hierarchy + RFC 7807 problem+json helpers.

Per ADR-010 (``.agent/adr/010-exception-hierarchy.md``):

* ``AppException`` is the base for all expected errors (4xx and 5xx).
  Subclasses set ``status_code``, ``error_code``, and ``title`` as class
  attributes. The handler in ``apps/api/api/main.py`` converts each
  instance into an RFC 7807 problem+json response with the request-id
  from the ADR-009 middleware as the ``instance`` field.

* ``problem_json_response(...)`` is the single helper that builds the
  body shape. It is also called by the ``HTTPException`` /
  ``RequestValidationError`` / catch-all handlers so every error path
  produces the same skeleton.

Response shape (RFC 7807):
    {
      "type":       "https://ai-news-scraper/errors/{error_code}",
      "title":      "<human-readable class title>",
      "status":     <int>,
      "detail":     "<human-readable detail>",
      "instance":   "<X-Request-ID from ADR-009 middleware>",
      "error_code": "<machine-readable code>",
      "context":    { ...optional kwargs from raise site... }   # omitted if empty
    }

PII posture (ADR-010 §10.5):
    Response bodies NEVER contain stack traces, file paths, hostnames,
    SQL queries, raw request bodies, Authorization headers, JWT
    tokens, or cookies. The ``context`` kwarg bag is caller-controlled;
    PR review must reject ``password`` / ``token`` / ``authorization``
    / ``cookie`` / ``body`` / ``query`` / ``headers`` as kwarg names.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi.responses import JSONResponse

from api.middleware.logging import get_request_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hierarchy — ``apps/api/api/exceptions.py``
# ---------------------------------------------------------------------------


class AppException(Exception):
    """Base for all expected API errors. 4xx/5xx, never leaks internals.

    Subclasses set ``status_code``, ``error_code``, and ``title`` as
    class attributes. ``detail`` is set per-raise; ``context`` is an
    arbitrary kwarg bag that serialises into the body (omitted when empty).
    """

    status_code: int = 500
    error_code: str = "internal_error"
    title: str = "Internal server error"

    def __init__(self, detail: str = "", **context: Any) -> None:
        super().__init__(detail)
        self.detail = detail
        self.context = context


class NotFoundError(AppException):
    """Resource lookup failed (article / feed / user not found, etc.)."""

    status_code = 404
    error_code = "not_found"
    title = "Resource not found"


class ValidationError(AppException):
    """Caller-supplied data failed hand-written validation (NOT Pydantic 422)."""

    status_code = 400
    error_code = "validation_error"
    title = "Validation error"


class AuthenticationError(AppException):
    """Caller is not authenticated (missing / invalid / expired token)."""

    status_code = 401
    error_code = "unauthenticated"
    title = "Authentication required"


class AuthorizationError(AppException):
    """Caller is authenticated but not permitted to act on this resource."""

    status_code = 403
    error_code = "forbidden"
    title = "Forbidden"


class UpstreamError(AppException):
    """An upstream service (RSS, OpenAI, ChromaDB) failed or timed out."""

    status_code = 502
    error_code = "upstream_error"
    title = "Upstream service failure"


# ---------------------------------------------------------------------------
# RFC 7807 problem+json helper
# ---------------------------------------------------------------------------


# Placeholder URN scheme — no docs endpoint is hosted yet (ADR-010 §10.5).
_TYPE_URI_BASE = "https://ai-news-scraper/errors/"


def _problem_body(
    *,
    error_code: str,
    title: str,
    status_code: int,
    detail: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an RFC 7807 problem+json body dict.

    ``context`` is omitted from the body when empty so the wire shape
    stays tight. ``instance`` is the current ``X-Request-ID`` from
    the ADR-009 middleware — empty string if no request is in scope
    (e.g. raised during app startup).
    """
    body: dict[str, Any] = {
        "type": f"{_TYPE_URI_BASE}{error_code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": get_request_id(),
        "error_code": error_code,
    }
    if context:
        body["context"] = context
    return body


def problem_json_response(
    *,
    error_code: str,
    title: str,
    status_code: int,
    detail: str,
    context: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a ``JSONResponse`` whose body conforms to RFC 7807.

    Headers are passed through (e.g. ``WWW-Authenticate: Bearer`` on 401).
    """
    return JSONResponse(
        status_code=status_code,
        content=_problem_body(
            error_code=error_code,
            title=title,
            status_code=status_code,
            detail=detail,
            context=context,
        ),
        headers=headers,
    )


__all__ = [
    "AppException",
    "NotFoundError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "UpstreamError",
    "problem_json_response",
]
