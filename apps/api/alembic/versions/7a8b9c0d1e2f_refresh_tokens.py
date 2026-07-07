"""add refresh_tokens table

Revision ID: 7a8b9c0d1e2f
Revises: 5d7e8f9a0b1c
Create Date: 2026-07-07

Task #36 / ADR-015 §15.9 — server-side logout invalidation. One new
table:

* ``refresh_tokens`` — opaque SHA-256-hashed refresh tokens issued
  on register / login. Logout sets ``revoked_at = now()``;
  ``/auth/refresh`` only honours rows where ``revoked_at IS NULL``.
  Cascade on user delete (parity with the rest of the auth surface).

Composite index ``ix_refresh_tokens_user_id_revoked_at`` on
``(user_id, revoked_at)`` supports both the per-user listing and
the equality lookup on a non-revoked row.

This file is HAND-WRITTEN against the SQLAlchemy model in
``apps/api/api/models/refresh_token.py`` (no autogenerate — see
ADR-006). Drift review follows below; the body must stay in sync
with the model column-for-column.

# DRIFT-FIX-2026-07-07: column-by-column drift review against model
# -------------------------------------------------------------
# Scope: apps/api/api/models/refresh_token.py
#
# refresh_tokens
#   id PK (UUID uuid4 default)                 — matches UUID(as_uuid=True) PK.
#   user_id UUID FK->users.id ON DELETE CASCADE NOT NULL — matches FK + cascade.
#   token_hash String(64) NOT NULL              — matches String(64) NOT NULL.
#   created_at TIMESTAMPTZ server_default=now() NOT NULL — matches DateTime(tz).
#   revoked_at TIMESTAMPTZ NULL                 — matches nullable DateTime(tz).
#
# Index:
#   ix_refresh_tokens_user_id_revoked_at ON refresh_tokens (user_id, revoked_at)
#     NOT NULL is fine on user_id; revoked_at IS NULL is the active-token
#     filter and Postgres indexes NULLs natively.
#
# Verdict: NO DRIFT — migration is hand-edited to be canonical against
# the live model. Do NOT regenerate via autogenerate without a follow-up
# ADR; this file is the source of truth until a new revision is added.
# -------------------------------------------------------------
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, Sequence[str], None] = "5d7e8f9a0b1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create refresh_tokens table + composite index (Task #36 / ADR-015)."""
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_refresh_tokens_user_id",
        ),
    )
    op.create_index(
        "ix_refresh_tokens_user_id_revoked_at",
        "refresh_tokens",
        ["user_id", "revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the composite index, then drop the table."""
    op.drop_index("ix_refresh_tokens_user_id_revoked_at", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
