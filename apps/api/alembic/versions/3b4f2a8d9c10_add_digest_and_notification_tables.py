"""add digest and notification tables

Revision ID: 3b4f2a8d9c10
Revises: 1890892bda24
Create Date: 2026-06-29 19:00:00.000000

Task #8 / ADR-012 — AI Brief daily digest + in-app notification inbox.

Two new tables:

* ``digests`` — one row per (user, date). Sections + overall summary are
  serialised JSON; ``delivery_status`` tracks the
  ``pending -> notified -> emailed | failed`` state machine.
* ``notifications`` — the in-app inbox. ``kind`` is one of
  ``brief_ready`` / ``brief_failed`` / ``system``; ``digest_id`` is set
  only for ``brief_ready``.

This file is HAND-WRITTEN against the SQLAlchemy models in
``apps/api/api/models/digest.py`` (no autogenerate — see ADR-006).
Drift review against models follows below; the body must stay in sync
with the models column-for-column.

# DRIFT-FIX-2026-06-29: column-by-column drift review against models
# -------------------------------------------------------------
# Scope: apps/api/api/models/digest.py + apps/api/api/models/user.py
#
# digests
#   id PK (UUID uuid4 default) | user_id UUID FK->users.id
#   ON DELETE CASCADE NOT NULL indexed | for_date Date indexed NOT NULL |
#   overall_summary Text NOT NULL default '' |
#   sections_json JSON NOT NULL default {} |
#   generated_at DateTime(tz) server_default=now() NOT NULL |
#   delivery_status String(32) NOT NULL default 'pending' |
#   email_message_id String(255) NULL |
#   UniqueConstraint(user_id, for_date).
#   Matches model exactly. No fixes needed.
#
# notifications
#   id PK (UUID uuid4 default) | user_id UUID FK->users.id
#   ON DELETE CASCADE NOT NULL indexed |
#   kind String(32) NOT NULL | title String(255) NOT NULL |
#   preview String(280) NOT NULL |
#   href String(512) NULL |
#   digest_id UUID FK->digests.id ON DELETE SET NULL NULL |
#   read Boolean NOT NULL default false indexed |
#   created_at DateTime(tz) server_default=now() NOT NULL |
#   read_at DateTime(tz) NULL.
#   Matches model exactly. No fixes needed.
#
# digest_unsubscribe_log (added 2026-06-29 — Devil M3+M6)
#   id PK (UUID uuid4 default) |
#   digest_id UUID FK->digests.id ON DELETE CASCADE NOT NULL indexed |
#   user_id UUID FK->users.id ON DELETE CASCADE NOT NULL indexed |
#   jwt_id String(64) NOT NULL UNIQUE  <-- DB-level replay guard |
#   consumed_at DateTime(tz) server_default=now() NOT NULL |
#   created_at DateTime(tz) server_default=now() NOT NULL.
#
# users (added email_digest_enabled — Devil M6)
#   email_digest_enabled Boolean NOT NULL default true.
#
# Verdict: extended to add digest_unsubscribe_log table + users.email_digest_enabled
# column + covering index ix_digests_for_date_status + partial index ix_notifications_user_unread
# per Devil Round 2 review (M3, M6, m2, m13).
# -------------------------------------------------------------
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3b4f2a8d9c10"
down_revision: Union[str, Sequence[str], None] = "1890892bda24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create digests + notifications tables (Task #8 / ADR-012).

    Extended 2026-06-29 per Devil Round 2 review:
      * digest_unsubscribe_log table (M3 + M6)
      * users.email_digest_enabled column (M6)
      * covering index ix_digests_for_date_status (m2)
      * partial index ix_notifications_user_unread WHERE read=false (m13)
    """
    # digests
    op.create_table(
        "digests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("for_date", sa.Date(), nullable=False),
        sa.Column("overall_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "sections_json",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "delivery_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("email_message_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_digests_user_id"
        ),
        sa.UniqueConstraint("user_id", "for_date", name="uq_digests_user_date"),
    )
    op.create_index("ix_digests_user_id", "digests", ["user_id"], unique=False)
    op.create_index("ix_digests_for_date", "digests", ["for_date"], unique=False)
    # Covering index for cron tick (m2): `WHERE for_date = today AND
    # delivery_status = 'pending'`.
    op.create_index(
        "ix_digests_for_date_status",
        "digests",
        ["for_date", "delivery_status"],
        unique=False,
    )

    # notifications
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("preview", sa.String(length=280), nullable=False),
        sa.Column("href", sa.String(length=512), nullable=True),
        sa.Column("digest_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_notifications_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["digest_id"],
            ["digests.id"],
            ondelete="SET NULL",
            name="fk_notifications_digest_id",
        ),
    )
    op.create_index(
        "ix_notifications_user_id", "notifications", ["user_id"], unique=False
    )
    op.create_index("ix_notifications_read", "notifications", ["read"], unique=False)
    # Partial index for the bell dropdown (m13):
    # `WHERE user_id = X AND read = false ORDER BY created_at DESC LIMIT 10`.
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "created_at"],
        unique=False,
        postgresql_where=sa.text("read = false"),
    )

    # users.email_digest_enabled (M6) — RFC 8058 unsubscribe target.
    op.add_column(
        "users",
        sa.Column(
            "email_digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # digest_unsubscribe_log (M3 + M6) — replay log for one-click tokens.
    # UNIQUE(jwt_id) is the authoritative DB-level replay guard; the
    # application-level check-then-INSERT is racy without it.
    op.create_table(
        "digest_unsubscribe_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("digest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jwt_id", sa.String(length=64), nullable=False),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["digest_id"],
            ["digests.id"],
            ondelete="CASCADE",
            name="fk_digest_unsubscribe_log_digest_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_digest_unsubscribe_log_user_id",
        ),
        sa.UniqueConstraint("jwt_id", name="uq_digest_unsubscribe_log_jwt_id"),
    )
    op.create_index(
        "ix_digest_unsubscribe_log_digest_id",
        "digest_unsubscribe_log",
        ["digest_id"],
        unique=False,
    )
    op.create_index(
        "ix_digest_unsubscribe_log_user_id",
        "digest_unsubscribe_log",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop notifications + digests + unsubscribe log + email_digest_enabled
    column (reverse FK / column order)."""
    # digest_unsubscribe_log
    op.drop_index(
        "ix_digest_unsubscribe_log_user_id", table_name="digest_unsubscribe_log"
    )
    op.drop_index(
        "ix_digest_unsubscribe_log_digest_id", table_name="digest_unsubscribe_log"
    )
    op.drop_table("digest_unsubscribe_log")

    # users.email_digest_enabled
    op.drop_column("users", "email_digest_enabled")

    # notifications
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_read", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    # digests
    op.drop_index("ix_digests_for_date_status", table_name="digests")
    op.drop_index("ix_digests_for_date", table_name="digests")
    op.drop_index("ix_digests_user_id", table_name="digests")
    op.drop_table("digests")
