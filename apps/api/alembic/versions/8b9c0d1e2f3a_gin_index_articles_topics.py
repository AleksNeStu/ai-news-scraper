"""GIN index on articles.topics for array-overlap search

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-07-08

The /search endpoint applies ``Article.topics && ARRAY[:topics]`` as a
Postgres-side filter (ADR-019 section 19.1 / Task #52). On a corpus
of any non-trivial size, this overlap predicate has no usable index
without GIN, so the planner falls back to a sequential scan on every
filtered search, even when Chroma has narrowed the candidate set to
50-200 ids.

The fix: a GIN index on ``articles.topics``. Postgres uses GIN for the
``&&`` (overlap) and ``@>`` (contains) array operators natively. The
index is built with the default ``gin__int_ops`` operator class which
covers string arrays out of the box.

Build cost: O(n) on the corpus, online by default in modern Postgres
(``CREATE INDEX`` without ``CONCURRENTLY`` takes a brief ACCESS
EXCLUSIVE lock; for a production deploy, the operator should run the
equivalent of ``CREATE INDEX CONCURRENTLY`` outside the migration, then
ship this migration once the index exists — this script will recreate
the index if it is missing on a fresh DB).

Ref: Task #52 post-hoc Devil review (MAJOR-1).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8b9c0d1e2f3a"
down_revision: str | None = "7a8b9c0d1e2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_articles_topics_gin "
        "ON articles USING GIN (topics)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_articles_topics_gin")
