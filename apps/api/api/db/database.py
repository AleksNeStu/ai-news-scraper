"""SQLAlchemy async database engine and session factory."""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from api.config import get_settings

_settings = get_settings()

# Under pytest-asyncio with function-scoped event loops, the default
# AsyncAdaptedQueuePool keeps connections bound to whichever loop
# first used them. asyncpg then schedules a cancel callback on that
# closed loop and raises "RuntimeError: Event loop is closed", which
# Starlette surfaces as a 500. Setting DATABASE_NULL_POOL=1 (done by
# tests/conftest.py before any api imports resolve) swaps the pool
# for NullPool so each engine.connect() opens a connection scoped to
# the calling loop and disposes it on return. Production behaviour
# is unchanged - the env var is unset in every runtime env
# (Docker compose, deploy) and the default branch keeps
# pool_size=10 / max_overflow=20.
if os.getenv("DATABASE_NULL_POOL") == "1":
    _engine_kwargs: dict = {
        "echo": False,
        "pool_pre_ping": True,
        "poolclass": NullPool,
    }
else:
    _engine_kwargs = {
        "echo": False,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
    }

engine = create_async_engine(
    _settings.database_url,
    **_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
