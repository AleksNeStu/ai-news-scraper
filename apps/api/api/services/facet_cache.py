"""Redis-backed cache wrapper for the facets response.

Task #53 / ADR-020.

Cache contract:

* Key shape: ``facets:{user_id}`` — ``user_id`` is part of the key so
  no cross-user leakage is possible even if a stale entry from user A
  is somehow served to user B (a defence-in-depth on top of the
  server-side ``WHERE user_id = :uid`` filter in the aggregator).
* TTL: 60 seconds (Task #53 hard requirement).
* Value: the JSON-serialised ``FacetsResponse``. Pydantic v2's
  ``model_dump_json`` produces canonical output (sorted keys, no
  Python-specific types), which is what ``JSONResponse`` would emit
  anyway — so the cache round-trip is bit-identical to a fresh query.
* Fail-open: any Redis error (timeout, unreachable, decode failure)
  is logged and falls through to the live aggregator. The endpoint
  must NEVER 500 because the cache is sick; the worst case is a
  slower response. The same posture is used by the rate limiter at
  ``api.middleware.rate_limit._enforce``.

We deliberately do NOT use the lifespan-cached global client pattern
from ``api.middleware.rate_limit`` because:

1. The lifespan ``_redis`` is built lazily and shared with the
   rate-limiter; we want facets to keep working when rate-limit Redis
   is being exercised. A dedicated client (still lazy) keeps the
   failure surfaces decoupled.
2. Tests need to monkeypatch ``facet_cache._get_redis`` (or
   ``api.routers.search._facet_cache_get``) to swap in
   ``fakeredis.FakeAsyncRedis`` — a dedicated module makes that
   import path obvious.

Cache miss path (``get_or_compute``) is built so the route handler
can stay one line: ``response = await get_or_compute(uid, db)``.

Singleton invariant (Task #53 Devil M-1)
-----------------------------------------

``_client`` (declared at module scope below) is a single shared
``redis.asyncio.Redis`` instance, built lazily on the first
``_get_redis()`` call. The invariant callers must respect is:

    At most ONE in-flight command on the client at any time.

``redis-py``'s asyncio client (and the underlying connection pool)
serialises commands onto a single connection. Using
``client.pipeline()`` / ``client.transaction()`` across an
``await`` boundary would interleave two coroutines' commands on the
same connection — Redis itself tolerates this (responses are tagged
by request ID) but our Pydantic round-trip (``await client.get(...)``
followed by ``await client.set(...)``) is NOT pipeline-safe in the
same way: a concurrent caller could land its ``DELETE`` between our
``GET`` and our ``SET`` and silently invalidate the entry we just
wrote. The current call sites (``_try_get_cached``,
``_try_set_cached``) are short, awaited atomically per
``get_or_compute``, and the route handler is the only caller — so
the invariant holds by construction.

If a future caller needs to issue multiple commands atomically,
they must ``async with client.pipeline(transaction=False)`` (NO
``MULTI``/``EXEC`` — Redis cluster forbids them) OR move to
``redis.asyncio.cluster.RedisCluster`` where each shard owns its
own connection. Adding any ``asyncio.gather`` over the client is a
bug.

Cross-reference: the same single-connection constraint is
documented at ``api.middleware.rate_limit`` (the rate limiter, by
contrast, opens a fresh connection per request via ``from_url``
because each call is a single command — different failure surface).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

import redis.asyncio as redis_async

from api.config import get_settings
from api.schemas.search import FacetsResponse

logger = logging.getLogger(__name__)
_settings = get_settings()

CACHE_TTL_SECONDS = 60
_KEY_PREFIX = "facets"

_client: redis_async.Redis | None = None


def _get_redis() -> redis_async.Redis:
    """Lazy singleton async Redis client (same pattern as rate_limit)."""
    global _client
    if _client is None:
        _client = redis_async.from_url(
            _settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _client


def _cache_key(user_id: UUID) -> str:
    """Per-user cache key. Including ``user_id`` in the key is the
    multi-tenant safety net: even a malicious or buggy operator-side
    cache flush cannot serve user A's facets to user B because the
    keys live in disjoint namespaces."""
    return f"{_KEY_PREFIX}:{user_id}"


async def _try_get_cached(user_id: UUID) -> FacetsResponse | None:
    """Return the cached ``FacetsResponse`` for ``user_id`` or None.

    Any Redis error is logged and yields None so the caller falls
    through to the aggregator. We deliberately do NOT raise — the
    cache is a performance optimisation, not a correctness primitive.
    """
    client = _get_redis()
    try:
        raw = await client.get(_cache_key(user_id))
    except Exception as e:  # noqa: BLE001 — fail-open by design
        logger.warning(
            "facet cache get failed, bypassing cache: user_id=%s err=%s",
            user_id,
            type(e).__name__,
        )
        return None
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Corrupt entry — drop it and let the aggregator repopulate.
        logger.warning("facet cache had non-JSON value, dropping: user_id=%s", user_id)
        try:
            await client.delete(_cache_key(user_id))
        except Exception as exc:  # noqa: BLE001
            logger.debug("facet cache delete failed: user_id=%s err=%s", user_id, exc)
        return None
    return FacetsResponse.model_validate(data)


async def _try_set_cached(user_id: UUID, response: FacetsResponse) -> None:
    """Persist ``response`` under ``facets:{user_id}`` with TTL=60s.

    Best-effort: a Redis SET failure must NOT fail the request. We
    ``await`` only ``set`` (the TTL is set atomically via the EX
    kwarg, no follow-up EXPIRE call needed).
    """
    client = _get_redis()
    try:
        await client.set(
            _cache_key(user_id),
            response.model_dump_json(),
            ex=CACHE_TTL_SECONDS,
        )
    except Exception as e:  # noqa: BLE001 — fail-open by design
        logger.warning(
            "facet cache set failed, response still served: user_id=%s err=%s",
            user_id,
            type(e).__name__,
        )


async def get_or_compute(
    user_id: UUID,
    compute: Callable[[], Awaitable[FacetsResponse]],
) -> tuple[FacetsResponse, bool]:
    """Return ``(response, cache_hit)``.

    On a cache hit, ``compute`` is never called and the cached payload
    is returned verbatim (the schema is the same — Pydantic v2
    re-validation is cheap). On a miss, ``compute()`` runs, the result
    is written back to Redis, and returned with ``cache_hit=False``.

    This shape (return both the value and the hit flag) lets the route
    handler attach a precise ``X-Cache: HIT|MISS`` header for ops
    debugging without forcing the cache layer to know about HTTP.
    """
    cached = await _try_get_cached(user_id)
    if cached is not None:
        return cached, True
    fresh = await compute()
    await _try_set_cached(user_id, fresh)
    return fresh, False


# Exposed for tests so they can monkeypatch the client / TTL without
# reaching into private module state.
def reset_for_tests() -> None:  # pragma: no cover — test helper
    global _client
    _client = None


__all__ = [
    "CACHE_TTL_SECONDS",
    # from ``_reset_for_tests`` because the function is in ``__all__``
    # and is part of the public test surface; the leading underscore
    # implied private module state, which was misleading).
    "_cache_key",
    "get_or_compute",
    "reset_for_tests",  # exposed for tests (Task #53 Devil L-2: renamed
]
