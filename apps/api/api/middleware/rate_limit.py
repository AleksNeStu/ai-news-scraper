"""Per-route Redis-backed rate limiter.

Lightweight INCR + EXPIRE token-bucket that uses the project's existing
``redis`` async client (deps already pulled in via ``redis[hiredis]`` for
brief queue work). Why hand-rolled rather than ``slowapi``:

* ``slowapi`` is not in ``pyproject.toml`` and the sandbox cannot
  ``poetry add`` new deps — see ``project-dev-env-no-deps`` memory.
* INCR + EXPIRE is a 6-line pattern; pulling a framework for it would
  be premature abstraction.
* The bucket key carries enough context that an operator can read
  Redis (``KEYS rl:*``) and immediately see who's being throttled.

Usage::

    from api.middleware.rate_limit import rate_limit_ip, rate_limit_user

    @router.post(\"/register\")
    async def register(
        payload: UserCreate,
        _rl: None = Depends(rate_limit_ip(\"register\", limit=5, window_s=3600)),
    ):
        ...

    @router.post(\"/scrape\")
    async def scrape(
        payload: ScrapeRequest,
        user_id: UUID = Depends(get_current_user_id),
        _rl = await rate_limit_user(\"scrape\", user_id, limit=30, window_s=3600),
    ):
        ...

Returns HTTP 429 with Retry-After when the bucket overflows. Bypassed
when ``APP_ENV == \"test\"`` so unit tests don't have to mock Redis for
every call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import redis.asyncio as redis_async
from fastapi import HTTPException, Request, status

from api.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

# Single shared async client — Redis async connections are safe to reuse
# across coroutines.
_redis: redis_async.Redis | None = None


def _get_redis() -> redis_async.Redis:
    """Lazily build the shared async Redis client.

    Deferred until first use so test environments without Redis still
    import cleanly (e.g. ``api.middleware.rate_limit`` may be imported
    by conftest helpers that don't actually call the limiter).
    """
    global _redis
    if _redis is None:
        _redis = redis_async.from_url(
            _settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis


@dataclass(frozen=True)
class _RateSpec:
    """Resolved bucket dimensions for a single call."""

    bucket: str
    limit: int
    window_s: int


def _client_ip(request: Request) -> str:
    """Return the canonical client IP, honouring ``X-Forwarded-For``.

    First-hop is the original client when the request sits behind a
    proxy (Dokploy / Traefik). Falls back to ``request.client.host``.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
    return request.client.host if request.client else "unknown"


async def _enforce(spec: _RateSpec) -> None:
    """Run the INCR + EXPIRE bucket for ``spec``; raise 429 on overflow."""
    client = _get_redis()
    # INCR + EXPIRE is the canonical token-bucket primitive: the first
    # INCR creates the key at 1, EXPIRE makes it vanish after
    # ``window_s``. We EXPIRE on every call (Redis is a no-op if TTL is
    # already set) so the window anchor stays at first hit.
    try:
        count = await client.incr(spec.bucket)
    except Exception as e:  # noqa: BLE001 — fail-open
        logger.warning(
            "rate-limit redis unreachable, failing open: bucket=%s err=%s",
            spec.bucket,
            type(e).__name__,
        )
        return
    if count == 1:
        await client.expire(spec.bucket, spec.window_s)
    if count > spec.limit:
        ttl = await client.ttl(spec.bucket)
        ttl = ttl if ttl > 0 else spec.window_s
        _raise_429(spec, ttl)


def _raise_429(spec: _RateSpec, retry_after: int) -> None:
    """Raise an HTTP 429 with Retry-After + X-RateLimit-* headers.

    Routed through ``HTTPException`` rather than ``AppException`` so the
    429 plumbing in ``apps/api/api/main.py::_title_for_status`` picks
    it up without expanding the AppException taxonomy.
    """
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            f"Rate limit exceeded: max {spec.limit} requests per "
            f"{spec.window_s // 60} minutes per identity."
        ),
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(spec.limit),
            "X-RateLimit-Remaining": "0",
        },
    )


def rate_limit_ip(name: str, *, limit: int, window_s: int):
    """Build a FastAPI dependency: enforce ``limit`` hits per IP per ``window_s``.

    For unauthenticated routes (e.g. ``/auth/register``) where there is
    no user identity yet.
    """

    async def _checker(request: Request) -> None:
        if _settings.app_env == "test":
            return
        spec = _RateSpec(
            bucket=f"rl:{name}:ip:{_client_ip(request)}",
            limit=limit,
            window_s=window_s,
        )
        await _enforce(spec)

    return _checker


async def rate_limit_user(
    name: str, user_id: Any, *, limit: int, window_s: int
) -> None:
    """Enforce ``limit`` hits per user per ``window_s`` (await directly).

    Called directly by the route handler (not as a ``Depends``) because
    ``user_id`` is itself the resolution of an upstream ``Depends``. This
    avoids a parallel Decode -> re-encode round-trip and lets the route
    fail-soft (skip enforcement) when user resolution succeeded but
    Redis is down.
    """
    if _settings.app_env == "test":
        return
    if user_id is None:
        return  # unauthenticated traffic routed elsewhere by the upstream 401
    ident = f"user:{user_id if isinstance(user_id, str) else UUID(str(user_id))}"
    spec = _RateSpec(bucket=f"rl:{name}:{ident}", limit=limit, window_s=window_s)
    await _enforce(spec)


__all__ = ["rate_limit_ip", "rate_limit_user"]
