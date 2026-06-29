"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.exceptions import AppException, problem_json_response
from api.middleware.logging import (
    RequestIDMiddleware,
    configure_logging,
    get_request_id,
)
from api.routers import (
    articles,
    auth,
    digest,
    feeds,
    health,
    notifications,
    scrape,
    search,
)
from api.scheduler.brief import BriefScheduler

logger = logging.getLogger(__name__)
_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Per ADR-009 §9.5: JSON logging setup runs at the top of lifespan
    # startup, before any router is mounted. Handlers attached by any
    # earlier ``logging.basicConfig`` are detached inside
    # ``configure_logging`` so we don't double-emit.
    configure_logging(_settings.log_level)
    logger.info("API starting up (env=%s)", _settings.app_env)
    # AI Brief scheduler — Task #8 / ADR-012 §12.3 + §12.11. Created
    # inside lifespan (NOT at import time) so test imports don't start
    # a background tick. Gated on `effective_digest_enabled` AND on the
    # OpenAI key being real (not the placeholder). When disabled, the
    # /digest router is also not mounted (see module-level below).
    scheduler: BriefScheduler | None = None
    if not _settings.effective_digest_enabled:
        logger.warning(
            "digest disabled (settings.effective_digest_enabled=False); "
            "scheduler NOT started, /digest router NOT mounted"
        )
    elif not _settings.openai_key_usable:
        logger.warning(
            "openai_api_key missing/placeholder; downgrading digest_enabled=False "
            "for this session; scheduler NOT started, /digest router NOT mounted"
        )
    else:
        scheduler = BriefScheduler()
        await scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()
        logger.info("API shutting down")


app = FastAPI(
    title="AI News Search API",
    version="0.1.0",
    description="Backend for AI News Scraper — Next.js 16 + FastAPI monorepo.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — must be registered AFTER RequestIDMiddleware so Starlette wraps
# CORS outermost. CORS preflight (OPTIONS) requests short-circuit inside
# CORS, so the request ID has to be set by middleware that runs even
# on preflight. Per ADR-009 §Implementation notes.
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handlers — RFC 7807 problem+json (ADR-010 §10.3).
#
# Every error path emits the same body skeleton. ``instance`` is the
# ``X-Request-ID`` from ADR-009, so log-search-to-response is a one-step
# lookup. Bodies never include stack traces, file paths, hostnames, SQL,
# raw bodies, or auth tokens — see ADR-010 §10.5.
# ---------------------------------------------------------------------------


@app.exception_handler(AppException)
async def _app_exception_handler(request: Request, exc: AppException):
    """Subclass-based errors (NotFoundError, AuthenticationError, ...)."""
    logger.warning(
        "app exception: %s %s -> %s (request_id=%s)",
        request.method,
        request.url.path,
        exc.status_code,
        get_request_id(),
        extra={"error_code": exc.error_code, "status_code": exc.status_code},
    )
    return problem_json_response(
        error_code=exc.error_code,
        title=exc.title,
        status_code=exc.status_code,
        detail=exc.detail,
        context=exc.context or None,
    )


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    """Backward compatibility for old ``raise HTTPException(...)`` call sites.

    Maps to problem+json with ``error_code="http_error"``; preserves any
    headers the caller passed (e.g. ``WWW-Authenticate: Bearer`` on 401).
    """
    logger.warning(
        "http exception: %s %s -> %s (request_id=%s, detail=%r)",
        request.method,
        request.url.path,
        exc.status_code,
        get_request_id(),
        exc.detail,
        extra={"error_code": "http_error", "status_code": exc.status_code},
    )
    return problem_json_response(
        error_code="http_error",
        title=_title_for_status(exc.status_code),
        status_code=exc.status_code,
        detail=str(exc.detail),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic body / query / path validation failure (HTTP 422)."""
    logger.warning(
        "validation error: %s %s (request_id=%s, errors=%d)",
        request.method,
        request.url.path,
        get_request_id(),
        len(exc.errors()),
        extra={"error_code": "validation_error", "status_code": 422},
    )
    # Future-work (ADR-010 §10.5): redact Authorization/Cookie/password
    # from exc.errors()['loc'] paths before serialisation. For now we
    # surface the raw Pydantic error list; PR review must reject routes
    # that ask for sensitive keys via body / query.
    return problem_json_response(
        error_code="validation_error",
        title="Validation error",
        status_code=422,
        detail="Request body or parameters failed validation.",
        context={"errors": exc.errors()},
    )


@app.exception_handler(500)
@app.exception_handler(Exception)
async def _catch_all_exception_handler(request: Request, exc: Exception):
    """Catch-all for any uncaught exception. Returns a generic 500 body.

    Registered for BOTH ``Exception`` (FastAPI's lookup walks the MRO
    during the per-request exception handler lookup) AND ``500``
    (Starlette's ``ServerErrorMiddleware`` reads ``app.exception_handlers[500]``
    at startup; without the ``500`` key, generic exceptions like
    ``RuntimeError`` are caught by ``ServerErrorMiddleware`` BEFORE
    FastAPI's handler can run — known FastAPI/Starlette integration
    quirk, see fastapi/fastapi#4025).

    Full traceback logged via ``logger.exception(...)`` so the operator
    can find it by request-id (the body's ``instance`` field). Never
    leaks internals to the client.
    """
    logger.exception(
        "unhandled exception: %s %s (request_id=%s)",
        request.method,
        request.url.path,
        get_request_id(),
        extra={"error_code": "internal_error", "status_code": 500},
    )
    return problem_json_response(
        error_code="internal_error",
        title="Internal server error",
        status_code=500,
        detail="An unexpected error occurred. See X-Request-ID for support.",
    )


def _title_for_status(status_code: int) -> str:
    """Map HTTP status code to a short RFC 7807 title (for HTTPException compat)."""
    return {
        400: "Bad request",
        401: "Authentication required",
        403: "Forbidden",
        404: "Resource not found",
        405: "Method not allowed",
        409: "Conflict",
        422: "Validation error",
        429: "Too many requests",
        500: "Internal server error",
        502: "Upstream service failure",
        503: "Service unavailable",
    }.get(status_code, "HTTP error")


# Routers — auth/articles/scrape/search/feeds/health/notifications are
# unconditional. The `/digest` router is gated on the same condition as
# the scheduler (ADR-012 §12.11): when disabled or the OpenAI key is
# missing, the endpoints 404 because the router simply isn't mounted.
# `/notifications` is NOT gated — notifications are independent of the
# brief pipeline.
app.include_router(auth.router)
app.include_router(articles.router)
app.include_router(scrape.router)
app.include_router(search.router)
app.include_router(feeds.router)
app.include_router(health.router)
app.include_router(notifications.router)
if _settings.effective_digest_enabled and _settings.openai_key_usable:
    app.include_router(digest.router)
else:
    logger.warning("digest router NOT mounted (disabled or openai_api_key missing)")
