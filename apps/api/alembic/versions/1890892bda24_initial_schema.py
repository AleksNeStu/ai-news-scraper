"""initial schema

Revision ID: 1890892bda24
Revises:
Create Date: 2026-06-28 20:43:14.302318

Mirrors the SQLAlchemy models in apps/api/api/models/:
    users, articles, feeds, feed_items.

# DRIFT-FIX-2026-06-29: column-by-column drift review against models
# -------------------------------------------------------------
# Scope: apps/api/api/models/{user,article,feed,feed_item}.py
# Method: compared every column, FK, unique constraint, and index
#         in this upgrade() against the mapped_column() / __table_args__
#         declarations on each model.
#
# Findings (per table):
#   users      - id PK / email String(320) NOT NULL unique-indexed /
#                hashed_password String(255) NOT NULL /
#                created_at DateTime(tz) server_default=now() NOT NULL.
#                Matches model exactly. No fixes needed.
#   articles   - id PK / user_id UUID FK->users.id ON DELETE CASCADE
#                nullable indexed / url Text NOT NULL indexed /
#                headline/body/summary Text nullable /
#                topics ARRAY(String) server_default='{}' /
#                source_domain String(255) nullable indexed /
#                publish_date DateTime(tz) nullable /
#                indexed_at DateTime(tz) server_default=now() NOT NULL
#                indexed / UniqueConstraint(user_id, url).
#                Matches model exactly. No fixes needed.
#   feeds      - id PK / user_id UUID FK->users.id ON DELETE CASCADE
#                NOT NULL indexed / feed_url Text NOT NULL /
#                title String(512) nullable /
#                description Text nullable /
#                last_polled DateTime(tz) nullable /
#                active Boolean NOT NULL server_default=true /
#                created_at DateTime(tz) server_default=now() NOT NULL /
#                UniqueConstraint(user_id, feed_url).
#                Matches model exactly. No fixes needed.
#   feed_items - id PK / feed_id UUID FK->feeds.id ON DELETE CASCADE
#                NOT NULL indexed /
#                article_id UUID FK->articles.id ON DELETE SET NULL
#                nullable indexed / guid Text NOT NULL /
#                title/url Text nullable /
#                fetched_at DateTime(tz) server_default=now() NOT NULL /
#                UniqueConstraint(feed_id, guid).
#                Matches model exactly. No fixes needed.
#
# Verdict: NO DRIFT - migration is hand-edited to be canonical against
# the live models. No upgrade() body changes were required. Do NOT
# regenerate via autogenerate without a follow-up ADR; this file is
# the source of truth until a new revision is added.
# -------------------------------------------------------------
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1890892bda24"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — create all four base tables."""
    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # articles
    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "topics",
            postgresql.ARRAY(sa.String()),
            server_default=sa.text("'{}'::text[]"),
            nullable=True,
        ),
        sa.Column("source_domain", sa.String(length=255), nullable=True),
        sa.Column("publish_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_articles_user_id"
        ),
        sa.UniqueConstraint("user_id", "url", name="uq_articles_user_url"),
    )
    op.create_index("ix_articles_url", "articles", ["url"], unique=False)
    op.create_index(
        "ix_articles_source_domain", "articles", ["source_domain"], unique=False
    )
    op.create_index("ix_articles_indexed_at", "articles", ["indexed_at"], unique=False)
    op.create_index("ix_articles_user_id", "articles", ["user_id"], unique=False)

    # feeds
    op.create_table(
        "feeds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("last_polled", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_feeds_user_id"
        ),
        sa.UniqueConstraint("user_id", "feed_url", name="uq_feeds_user_url"),
    )
    op.create_index("ix_feeds_user_id", "feeds", ["user_id"], unique=False)

    # feed_items
    op.create_table(
        "feed_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("feed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("guid", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["feed_id"], ["feeds.id"], ondelete="CASCADE", name="fk_feed_items_feed_id"
        ),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            ondelete="SET NULL",
            name="fk_feed_items_article_id",
        ),
        sa.UniqueConstraint("feed_id", "guid", name="uq_feed_items_feed_guid"),
    )
    op.create_index("ix_feed_items_feed_id", "feed_items", ["feed_id"], unique=False)
    op.create_index(
        "ix_feed_items_article_id", "feed_items", ["article_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema — drop in reverse FK order."""
    op.drop_index("ix_feed_items_article_id", table_name="feed_items")
    op.drop_index("ix_feed_items_feed_id", table_name="feed_items")
    op.drop_table("feed_items")

    op.drop_index("ix_feeds_user_id", table_name="feeds")
    op.drop_table("feeds")

    op.drop_index("ix_articles_user_id", table_name="articles")
    op.drop_index("ix_articles_indexed_at", table_name="articles")
    op.drop_index("ix_articles_source_domain", table_name="articles")
    op.drop_index("ix_articles_url", table_name="articles")
    op.drop_table("articles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
