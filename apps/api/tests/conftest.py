"""Shared pytest fixtures for apps/api tests.

Key fixtures:
    * ``client`` — httpx AsyncClient against the FastAPI app, lifespan-aware.
    * ``db_session`` — per-test async DB session wrapped in a savepoint
      that rolls back at the end. No DROP/CREATE per test; no leaks.
    * ``auth_user`` — registers a test user and returns the JWT
      plus a ready-to-use ``Authorization`` header.

Requires a reachable Postgres at ``$DATABASE_URL``. If the DB is
unavailable the fixtures fail loudly so the missing service is
obvious — never silently skip.

Note on engine choice: the production ``engine`` (api.db.database) uses
a connection pool sized for concurrent traffic. That pool holds
connections bound to whichever event loop first used them, which
breaks pytest-asyncio's per-test event loop. We build a
``test_engine`` with ``NullPool`` so each connection is opened and
closed within the calling event loop — no cross-loop reuse.
"""

from __future__ import annotations

# IMPORTANT: must run BEFORE the api.* imports below. database.engine
# is created at module import time with the production
# AsyncAdaptedQueuePool; pytest-asyncio gives each test a
# function-scoped event loop, so the pool's cached connections end
# up bound to a closed loop and asyncpg raises "Event loop is
# closed" -> Starlette 500. The env-var branch in api/db/database.py
# reads DATABASE_NULL_POOL at import time and uses NullPool when
# set. Do not move this below the imports.
import os

os.environ.setdefault("DATABASE_NULL_POOL", "1")

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from api.config import get_settings
from api.main import app
from api.models.user import User
from api.services.auth import create_token, hash_password

_settings = get_settings()

# Test engine: NullPool (no pooling) so connections are scoped to a
# single event loop. Created once at module import — pytest-asyncio
# gives the fixture a function-scoped loop to run on, and NullPool
# keeps each connection from outliving that loop.
test_engine = create_async_engine(
    _settings.database_url,
    echo=False,
    poolclass=NullPool,
)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Per-test DB session with transactional rollback.

    Opens a connection, begins a transaction, and binds a session to
    it. The transaction is rolled back at the end so tests never leak
    rows and never need DROP/CREATE.

    ``loop_scope="function"`` aligns the fixture's event loop with the
    test body's loop. The ``test_engine`` uses ``NullPool`` so each
    ``engine.connect()`` creates a fresh connection bound to the
    current event loop (the production pool would hold connections
    across loops, raising 'Task ... got Future ... attached to a
    different loop').
    """
    async with test_engine.connect() as connection:
        await connection.begin()
        async with TestAsyncSessionLocal(bind=connection) as session:
            try:
                yield session
            finally:
                await connection.rollback()


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Lifespan-aware httpx AsyncClient against the FastAPI app.

    ASGITransport does not auto-run ``lifespan`` events, so we drive
    the lifespan context explicitly. Anything the app touches at
    startup will be exercised.

    ``raise_app_exceptions=False`` — Starlette's ``ServerErrorMiddleware``
    re-raises unhandled exceptions AFTER sending a 500 response (so
    servers can log them). In test mode we want the response, not the
    re-raise. Tests that explicitly assert exception behaviour use
    ``pytest.raises(...)`` against ``ASGITransport(app=app)`` directly.
    Production behaviour is unchanged — see starlette/middleware/errors.py.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as ac,
    ):
        yield ac


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def auth_user(
    db_session: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Registers a test user and mints a JWT for them.

    We deliberately do NOT call the HTTP ``/auth/login`` endpoint here:
    the login endpoint reads from its own ``AsyncSessionLocal()`` —
    a separate connection/transaction from this fixture's
    ``db_session`` — and so cannot see the just-flushed user row.
    Instead we call ``create_token`` directly, which is the same
    code path the real login uses after the password check.

    Returns a dict with the ``User`` model instance, the bearer
    ``token``, and a ready-to-use ``headers`` dict.
    """
    user = User(
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
    )
    db_session.add(user)
    await db_session.flush()

    token = create_token(user.id, user.email)

    yield {
        "user": user,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


async def register_user_and_login(
    client: AsyncClient, email: str, password: str
) -> tuple[dict[str, Any], str]:
    """Register a new user via HTTP, then log in via HTTP.

    Returns ``(user_data, token)`` — the user dict from the register
    response and the bearer token from the login response. Both HTTP
    flows are exercised; intended for tests that want to assert
    register + login work end-to-end (vs ``auth_user`` which mints
    a JWT directly without hitting either endpoint).
    """
    register_resp = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert register_resp.status_code == 201, register_resp.text
    register_body = register_resp.json()
    user_data = register_body["user"]

    login_resp = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["token"]

    return user_data, token


# ---------------------------------------------------------------------------
# Autouse — neutralise the per-IP register rate limit so tests that hit
# /auth/register via HTTP (test_feeds_export.py::register_user_and_login,
# test_feeds_bulk.py, etc.) don't trip the 5/3600 bucket on a Redis-backed
# dev stack. Mirrors test_feeds_bulk.py::_disable_register_rate_limit.
# CI ships without Redis (the limit fails open there already); this
# fixture only matters for ``make test-api`` against the Compose stack.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _disable_register_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub ``rate_limit._enforce`` to a no-op for the duration of each test."""
    from api.middleware import rate_limit as rate_limit_module

    async def _no_enforce(spec: object) -> None:
        return None

    monkeypatch.setattr(rate_limit_module, "_enforce", _no_enforce)
