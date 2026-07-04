"""Apply ``apps/api/scripts/seed.sql`` against the configured Postgres URL.

Used as the second stage of the ``migrate`` one-shot service in
``docker-compose.yml`` (after ``alembic upgrade head``). Both steps are
idempotent, so ``docker compose up`` re-runs them safely on every up —
Alembic no-ops when already at head, and every INSERT in ``seed.sql``
uses ``ON CONFLICT DO NOTHING`` keyed on each table's unique constraint.

Manual use from a dev shell:

    cd apps/api
    poetry run python -m api.scripts.seed

Reads ``DATABASE_URL`` (async, asyncpg-prefixed). Splits ``seed.sql`` on
top-level ``;`` after stripping line comments. The seed file contains
pure DML and no PL/pgSQL blocks, so a naive split is correct; if the
seed grows to include functions / DO blocks, swap in a real SQL parser
(e.g. ``sqlglot``).

DEV-ONLY seed data. The committed bcrypt hash is for password
``dev-only-do-not-use-in-prod``. Never run this against production.
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


# This script lives at apps/api/api/scripts/seed.py — go up three levels to
# apps/api/, then into scripts/seed.sql.
SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed.sql"

# Strip SQL line comments (--...) before splitting. Block comments are not
# expected in this seed file; if needed, add ``/* ... */`` handling here.
_COMMENT_RE = re.compile(r"--[^\n]*")


def _split_statements(sql: str) -> list[str]:
    cleaned = _COMMENT_RE.sub("", sql)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if not SEED_PATH.exists():
        raise SystemExit(f"seed file not found: {SEED_PATH}")

    statements = _split_statements(SEED_PATH.read_text(encoding="utf-8"))
    if not statements:
        raise SystemExit(f"{SEED_PATH} contains no statements")

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            for stmt in statements:
                await conn.execute(text(stmt))
    finally:
        await engine.dispose()

    print(f"[seed] applied {len(statements)} statements from {SEED_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
