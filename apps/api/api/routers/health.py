"""Readiness endpoint for external monitors (Uptime Kuma, Grafana, etc.).

Per ADR-008: returns 200 with ``status: ok`` when Postgres + ChromaDB are
reachable; 503 with ``status: degraded`` when at least one check fails.
The per-check body identifies which dependency is down. Stack traces,
hostnames, and connection strings never appear in the response.

Routes:
    GET /health -> readiness probe (no auth, per ADR-008 §8.2)
"""

from __future__ import annotations

import asyncio
import logging

import chromadb
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["meta"])
settings = get_settings()

# Per-check timeouts: fail fast so a stalled dependency never hangs the
# probe (which would itself look like an outage to the monitor).
_CHECK_TIMEOUT_S = 2.0

# Cap the error reason string we leak to the response body. We only
# surface the exception class name (per ADR-008 §8.6), but cap defensively
# in case a future change widens what's exposed.
_MAX_ERROR_LEN = 200


def _format_error(exc: BaseException) -> str:
    """Return ``error: <ExceptionType>`` — class name only.

    Per ADR-008 §8.6: no message, no traceback, no hostnames, no paths.
    """
    return f"error: {type(exc).__name__}"[:_MAX_ERROR_LEN]


async def _check_postgres() -> tuple[str, str | None]:
    """Open a session via ``AsyncSessionLocal``, run ``SELECT 1``, close.

    Returns ``("ok", None)`` on success or ``("error", formatted_reason)``
    on any exception. The reason is class-name only — safe to expose.
    """
    # Local import avoids a potential cycle on app startup and lets
    # tests monkeypatch ``api.routers.health._check_postgres`` cleanly.
    from api.db.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            result = await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=_CHECK_TIMEOUT_S,
            )
            value = result.scalar()
            if value == 1:
                return ("ok", None)
            return ("error", f"unexpected scalar: {value!r}"[:_MAX_ERROR_LEN])
    except Exception as e:  # noqa: BLE001 — probe must catch everything
        logger.warning("health check failed: postgres", exc_info=True)
        return ("error", _format_error(e))


async def _check_chroma() -> tuple[str, str | None]:
    """HTTP heartbeat against the ChromaDB server.

    Constructs ``chromadb.HttpClient`` directly (per ADR-008 §8.4) so we
    do not pull in the ``ChromaVectorStore`` HTTP→persistent fallback
    path — that conflates "store available" with "HTTP server up."
    ``.heartbeat()`` is synchronous in chromadb 0.5.x, so we wrap it in
    ``asyncio.to_thread`` to keep the event loop cooperative.
    """
    try:
        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        await asyncio.wait_for(
            asyncio.to_thread(client.heartbeat),
            timeout=_CHECK_TIMEOUT_S,
        )
        return ("ok", None)
    except Exception as e:  # noqa: BLE001 — probe must catch everything
        logger.warning("health check failed: chroma", exc_info=True)
        return ("error", _format_error(e))


@router.get(
    "/health",
    summary="Readiness check (Postgres + ChromaDB)",
    response_description="Aggregate readiness plus per-check status strings.",
)
async def health() -> JSONResponse:
    """Aggregate readiness signal.

    Runs both checks concurrently. Returns 200 when both pass and 503
    when any check fails. The body shape is constant across both codes
    so monitors that only care about the status code (Uptime Kuma,
    Alertmanager) work without parsing JSON, while dashboards that want
    per-dependency detail can read the ``checks`` map.
    """
    pg_result, ch_result = await asyncio.gather(
        _check_postgres(),
        _check_chroma(),
    )
    pg_status_str, pg_err_str = pg_result
    ch_status_str, ch_err_str = ch_result

    overall_ok = pg_err_str is None and ch_err_str is None
    body = {
        "status": "ok" if overall_ok else "degraded",
        "env": settings.app_env,
        "checks": {
            "postgres": "ok" if pg_err_str is None else pg_err_str,
            "chroma": "ok" if ch_err_str is None else ch_err_str,
        },
    }
    return JSONResponse(
        status_code=200 if overall_ok else 503,
        content=body,
    )
