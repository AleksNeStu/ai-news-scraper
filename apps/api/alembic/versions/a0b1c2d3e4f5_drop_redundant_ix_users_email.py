"""drop redundant ix_users_email unique index

Revision ID: a0b1c2d3e4f5
Revises: 9c0d1e2f3a4b
Create Date: 2026-07-12

Task #31 / Devil M2 on Task #2 — the initial migration
(1890892bda24_initial_schema.py) creates two unique objects on
``users.email``:

* ``UniqueConstraint("email", name="uq_users_email")`` (line 83)
* ``op.create_index("ix_users_email", "users", ["email"], unique=True)``
  (line 85)

Postgres enforces uniqueness once per column, so the second object is
redundant at the DDL level. It violates the ADR-006 §2.1 spirit
("single unique source per column") and SQLAlchemy 2.x autogenerate
emits only one of them when the model is the source of truth, so the
duplicate currently masks autogenerate drift.

This migration drops the redundant unique index. The
``uq_users_email`` ``UniqueConstraint`` stays. The model in
``apps/api/api/models/user.py`` was updated in the same atomic commit
to declare the constraint explicitly via ``__table_args__`` (matching
the migration's named constraint) and to drop the column-level
``unique=True`` / ``index=True`` markers that would otherwise cause
SQLAlchemy to emit a different name on the next autogenerate.

Downgrade recreates the unique index for a clean reverse path.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a0b1c2d3e4f5"
down_revision: str | None = "9c0d1e2f3a4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the redundant unique index on users.email (Task #31 / Devil M2)."""
    op.drop_index("ix_users_email", table_name="users")


def downgrade() -> None:
    """Recreate the unique index on users.email (round-trip safe)."""
    op.create_index("ix_users_email", "users", ["email"], unique=True)
