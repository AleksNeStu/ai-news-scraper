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
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import AsyncSessionLocal, engine
from api.main import app
from api.models.user import User
from api.services.auth import create_token, hash_password


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Per-test DB session with transactional rollback.

    Opens a connection, begins a transaction, and binds a session to
    it. The transaction is rolled back at the end so tests never leak
    rows and never need DROP/CREATE.

    ``loop_scope="function"`` aligns the fixture's event loop with the
    test body's loop so shared resources (engine connection, session)
    work across the setup/teardown boundary. pytest-asyncio 0.23+
    introduced per-fixture loop scoping; without this argument,
    fixtures default to their own loop scope and raise
    'Task ... got Future ... attached to a different loop'.
    """
    async with engine.connect() as connection:
        await connection.begin()
        async with AsyncSessionLocal(bind=connection) as session:
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
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
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
