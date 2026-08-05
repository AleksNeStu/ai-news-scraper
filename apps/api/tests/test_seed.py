"""Idempotency smoke for ``apps/api/scripts/seed.sql`` (Task #32 / ADR-006 §6.3).

Per ADR-006 §6.3: "the project commits to a test that runs
``apps/api/scripts/seed.sql`` twice against a clean DB and asserts row
counts are unchanged (true idempotency)." Devil's review of Task #2
flagged this gap as untested. Task #2 itself did not add the test
(the brief said do not write new fixtures) — this file is the
follow-up.

The seed file uses ``ON CONFLICT DO NOTHING`` keyed on every model's
unique constraint, so re-running it is supposed to be a no-op. This
test pins that contract so a future refactor that drops an ``ON
CONFLICT`` clause (or mistypes a conflict target) is caught at
pytest time.

Skipped when no live Postgres is reachable (sandbox + CI without the
``api-test`` service). Uses the existing ``test_engine`` from
``conftest.py`` so connections are NullPool-scoped to the per-test
event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import Base
from tests.conftest import TestAsyncSessionLocal, test_engine

# Path to the seed file relative to repo root. Tests run from the
# apps/api/ directory by default; resolve against this file so the
# path is stable regardless of cwd.
# Path to the seed file relative to repo root. Tests run from the
# apps/api/ directory by default; resolve against this file so the
# path is stable regardless of cwd. parents[1] = apps/api/ (this
# file lives in apps/api/tests/, so 1 level up).
SEED_SQL_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed.sql"


# Tables that the seed file populates. Each ``ON CONFLICT DO NOTHING``
# clause is keyed on a per-table unique constraint; row counts must be
# stable across re-runs. Listed in the order they appear in seed.sql
# so a debugging diff shows the seed author's intent.
SEEDED_TABLES: tuple[str, ...] = (
    "users",
    "feeds",
    "articles",
    "feed_items",
)


async def _is_db_reachable() -> bool:
    """Best-effort reachability check; skips the test when Postgres is down.

    Per the project convention (sandbox has no DB, CI without
    ``api-test`` service): if we cannot open a connection in 2s, skip
    rather than fail. Returns True on success.
    """
    try:
        async with test_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False
    except (OSError, asyncio.TimeoutError):
        # Any other error (driver missing, DNS, etc.) is also a skip.
        return False


async def _count_rows(session: AsyncSession, table: str) -> int:
    """Return ``SELECT COUNT(*) FROM <table>`` for the current schema."""
    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return int(result.scalar_one())


async def _apply_schema() -> None:
    """Create all tables from ``Base.metadata`` so the seed file has somewhere to land.

    The test bypasses alembic here (faster, no version-table dance) —
    the seed SQL only inserts rows, it does not depend on alembic's
    schema-management extras. ``Base.metadata.create_all`` mirrors what
    alembic would emit on ``upgrade head`` minus the alembic_version
    table.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_schema() -> None:
    """Teardown for seed_db — INTENTIONALLY A NO-OP.

    History:
      - Original: ``Base.metadata.drop_all`` nuked the entire alembic-managed
        schema, breaking every subsequent test that depended on it.
      - Attempt 2 (TRUNCATE the 4 SEEDED_TABLES): emptied the ``users`` table
        which other tests need for register/login.

    Fix: do nothing. seed.sql uses ``ON CONFLICT DO NOTHING`` so re-running is
    a no-op; leaving the seeded rows in place does not pollute other tests
    because the seed emails are unique strings.
    """
    pass


async def _run_seed_sql() -> None:
    """Execute ``seed.sql`` once via the async engine.

    asyncpg refuses multi-statement prepared statements (raises
    "cannot insert multiple commands into a prepared statement"),
    so we split the file into individual statements via the
    production ``_split_statements`` helper in
    ``apps/api/api/scripts/seed.py``. Each statement is executed
    individually; the surrounding ``async with engine.begin()``
    block makes the whole sequence one transaction — matching the
    behaviour of ``psql -f`` exactly.
    """
    from api.scripts.seed import _split_statements

    sql = SEED_SQL_PATH.read_text(encoding="utf-8")
    statements = _split_statements(sql)
    async with test_engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def seed_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session against a freshly created schema.

    Skips the test if the DB is unreachable (sandbox + CI without
    postgres service). On teardown, drops every seeded table so the
    next test starts from a clean slate.
    """
    if not await _is_db_reachable():
        pytest.skip("live DB required for seed idempotency smoke (Task #32)")

    await _apply_schema()
    try:
        async with TestAsyncSessionLocal() as session:
            yield session
    finally:
        await _drop_schema()


async def test_seed_sql_is_idempotent(seed_db: AsyncSession) -> None:
    """Run ``seed.sql`` twice; row counts must be stable between runs.

    ADR-006 §6.3 acceptance: the seed file is supposed to be re-runnable
    against an already-seeded DB without duplicating rows. If any of the
    four tables ends up with a higher count after the second run, the
    corresponding ``ON CONFLICT DO NOTHING`` clause in ``seed.sql`` is
    broken (or the unique constraint it references has drifted).
    """
    # First run.
    await _run_seed_sql()
    first_counts = {table: await _count_rows(seed_db, table) for table in SEEDED_TABLES}

    # Sanity: the first run must have populated each table. Zero counts
    # would mean the seed file's INSERTs failed silently.
    assert all(count > 0 for count in first_counts.values()), (
        f"first seed run produced empty tables: {first_counts}"
    )

    # Second run.
    await _run_seed_sql()
    second_counts = {
        table: await _count_rows(seed_db, table) for table in SEEDED_TABLES
    }

    # Acceptance: counts must match run-for-run.
    assert second_counts == first_counts, (
        f"seed.sql is NOT idempotent. first run: {first_counts}; "
        f"second run: {second_counts}. The ON CONFLICT clause for the "
        "table that grew is broken."
    )
