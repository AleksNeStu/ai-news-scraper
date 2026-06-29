"""add article score columns

Revision ID: 4c5d6e7f8a9b
Revises: 3b4f2a8d9c10
Create Date: 2026-06-29 20:00:00.000000

Task #9 / ADR-013 §13.4 — tiered curation schema.

Three nullable columns on ``articles``:

* ``score``     ``DOUBLE PRECISION`` — 0.0..1.0; NULL when never scored.
* ``scored_at`` ``TIMESTAMPTZ``      — when ``score`` was last computed.
* ``tier``      ``VARCHAR(16)``      — denormalized bucket
  (``must_read`` / ``recommended`` / ``worth_a_look`` / ``low_priority``)
  mirroring ``tier_from_score(score)`` on write so the composite index
  below stays usable for ``WHERE tier = ?`` filters.

Plus one composite index:

* ``ix_articles_tier_scored_at`` ON articles (tier, scored_at)
  — supports the ``?tier=`` filter and the ``?group_by_tier=true``
  ordering. Monotonic; small footprint (tier has 4 distinct values + NULL).

This file is HAND-WRITTEN against the SQLAlchemy model in
``apps/api/api/models/article.py`` (no autogenerate — see ADR-006).
Drift review follows below; the body must stay in sync with the model
column-for-column.

# DRIFT-FIX-2026-06-29: column-by-column drift review against models
# -------------------------------------------------------------
# Scope: apps/api/api/models/article.py
#
# New columns on articles:
#   score     DOUBLE PRECISION NULL                — matches Float().
#   scored_at TIMESTAMPTZ      NULL                — matches DateTime(tz).
#   tier      VARCHAR(16)      NULL                — matches String(16).
#
# New index:
#   ix_articles_tier_scored_at ON articles (tier, scored_at)
#     NOT NULL is fine — Postgres indexes NULLs natively for the
#     composite, and the SQL planner picks it for both
#     ``WHERE tier = ?`` and ``WHERE tier = ? ORDER BY scored_at DESC``.
#
# Verdict: NO DRIFT — migration is hand-edited to be canonical against
# the live model. No upgrade() body changes were required. Do NOT
# regenerate via autogenerate without a follow-up ADR; this file is
# the source of truth until a new revision is added.
# -------------------------------------------------------------
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c5d6e7f8a9b"
down_revision: Union[str, Sequence[str], None] = "3b4f2a8d9c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add score / scored_at / tier columns + composite index (Task #9)."""
    op.add_column(
        "articles",
        sa.Column("score", sa.Double(), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("tier", sa.String(length=16), nullable=True),
    )
    op.create_index(
        "ix_articles_tier_scored_at",
        "articles",
        ["tier", "scored_at"],
        unique=False,
    )


def downgrade() -> None:
    """Reverse: drop composite index, then drop the three columns."""
    op.drop_index("ix_articles_tier_scored_at", table_name="articles")
    op.drop_column("articles", "tier")
    op.drop_column("articles", "scored_at")
    op.drop_column("articles", "score")
