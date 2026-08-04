"""add shared_links + shared_link_visits tables

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-07-09

Task #33 / ADR-021 — public read-only shareable article links. Two new
tables; both live under the shareable-link feature. No data migration
is required (Task #33 is greenfield — no prior share rows exist).

``shared_links``
    The mint record. One row per (article, owner) pair that ever asked
    for a public URL. ``token_hash`` is the SHA-256 hex digest of the
    raw ``secrets.token_urlsafe(32)`` token; the raw token is only ever
    returned in the ``POST /share`` response body and never persisted
    (ADR-021 §21.1, §21.9). The unique index on ``token_hash`` is the
    lookup key for ``GET /s/{token}``.

``shared_link_visits``
    Append-only audit log of unauthenticated reads. The
    ``(shared_link_id, visited_at_bucket)`` UNIQUE constraint is the
    per-second de-dupe key — concurrent GETs from the same visitor
    collapse to one row, and ``SELECT COUNT(*)`` is the live visit
    counter (ADR-021 §21.6). ``shared_links.visits`` is a cached
    roll-up refreshed by a background job; it is NOT written on the
    request path.

Cascade strategy: both FKs are ``ON DELETE CASCADE``. Article delete
retracts every share of that article (GDPR posture — one DELETE is
enough). User delete cascades to articles and from there to share
rows, so account deletion also retracts shares transitively.

Indexes:
* ``ix_shared_links_token_hash`` — UNIQUE; created automatically by
  ``unique=True`` on the column, but listed here explicitly because
  the ``GET /s/{token}`` lookup is index-driven.
* ``ix_shared_links_article_id`` — supports the cascade's reverse
  lookup (and future "list shares of this article" admin views).
* ``ix_shared_links_expires_at`` — supports the GC job
  ``DELETE FROM shared_links WHERE expires_at < NOW()``.
* ``ix_shared_link_visits_link`` — supports the
  ``SELECT COUNT(*) WHERE shared_link_id = ?`` on the read path.

This file is HAND-WRITTEN against the SQLAlchemy model in
``apps/api/api/models/shared_link.py`` (no autogenerate — see ADR-006).
Drift review follows below; the body must stay in sync with the model
column-for-column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9c0d1e2f3a4b"
down_revision: str | None = "8b9c0d1e2f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create shared_links + shared_link_visits tables (Task #33 / ADR-021)."""
    # ``pgcrypto`` provides ``gen_random_uuid()`` (ADR-021 §21.9). The
    # ``enable_pgcrypto`` migration (5d7e8f9a0b1c) already created the
    # extension, so the function is available in the target DB.
    op.create_table(
        "shared_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "visits",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            ondelete="CASCADE",
            name="fk_shared_links_article_id",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_shared_links_created_by",
        ),
        sa.UniqueConstraint("token_hash", name="uq_shared_links_token_hash"),
    )
    op.create_index(
        "ix_shared_links_article_id",
        "shared_links",
        ["article_id"],
        unique=False,
    )
    op.create_index(
        "ix_shared_links_expires_at",
        "shared_links",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "shared_link_visits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "shared_link_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "visited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "visited_at_bucket",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["shared_link_id"],
            ["shared_links.id"],
            ondelete="CASCADE",
            name="fk_shared_link_visits_shared_link_id",
        ),
        sa.UniqueConstraint(
            "shared_link_id",
            "visited_at_bucket",
            name="uq_shared_link_visits_link_bucket",
        ),
    )
    op.create_index(
        "ix_shared_link_visits_link",
        "shared_link_visits",
        ["shared_link_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the visit log first (FK-dependent), then shared_links."""
    op.drop_index("ix_shared_link_visits_link", table_name="shared_link_visits")
    op.drop_table("shared_link_visits")
    op.drop_index("ix_shared_links_expires_at", table_name="shared_links")
    op.drop_index("ix_shared_links_article_id", table_name="shared_links")
    op.drop_table("shared_links")