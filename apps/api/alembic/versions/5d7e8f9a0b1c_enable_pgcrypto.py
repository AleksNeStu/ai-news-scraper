"""enable pgcrypto extension

Revision ID: 5d7e8f9a0b1c
Revises: 4c5d6e7f8a9b
Create Date: 2026-07-06

The fresh-DB DoD for first-run onboarding requires pgcrypto so future
use of pgcrypto-backed bcrypt helpers and crypt() is available.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "5d7e8f9a0b1c"
down_revision: str | None = "4c5d6e7f8a9b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
