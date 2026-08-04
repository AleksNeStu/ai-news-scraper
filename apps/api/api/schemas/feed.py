"""Feed / RSS schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class FeedCreate(BaseModel):
    feed_url: HttpUrl


class FeedOut(BaseModel):
    id: UUID
    feed_url: str
    title: str | None = None
    description: str | None = None
    last_polled: datetime | None = None
    active: bool
    item_count: int = 0
    created_at: datetime


class FeedListResponse(BaseModel):
    items: list[FeedOut]
    total: int


class FeedItemOut(BaseModel):
    id: UUID
    feed_id: UUID
    article_id: UUID | None = None
    guid: str
    title: str | None = None
    url: str | None = None
    fetched_at: datetime


# --- OPML bulk import (Task #35, ADR-024) ---


class OpmlFeedRef(BaseModel):
    """Single feed reference parsed from OPML by the web client.

    Mirrors the TS `OpmlFeedRef` in `packages/shared/src/types.ts`.
    Naming convention: snake_case here (Pydantic), camelCase on the wire
    (FastAPI auto-aliases via Pydantic v2 alias_generator — see ADR-024
    §24 "HttpUrl field naming convention").
    """

    model_config = ConfigDict(populate_by_name=True)

    xml_url: HttpUrl = Field(
        ..., alias="xmlUrl", description="RSS/Atom feed URL"
    )
    title: str | None = Field(default=None, description="OPML outline title/text")
    category: str | None = Field(
        default=None,
        description=(
            "OPML outline folder (e.g. 'Tech > AI'). Discarded by the v1 "
            "backend; plumbed through for forward-compat with v2 category "
            "grouping on /feeds."
        ),
    )


class BulkImportRequest(BaseModel):
    """Body of `POST /feeds/bulk`.

    Hard-capped at 500 items to bound request size and the synchronous
    parse tail (ADR-024 §24.2). Mirrors the TS `BulkImportRequest` in
    `packages/shared/src/types.ts`.
    """

    feeds: list[OpmlFeedRef] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Feed references parsed from the user's OPML upload (1..500).",
    )


class BulkImportFailure(BaseModel):
    """One feed in a bulk import that could not be created.

    Mirrors the TS `BulkImportFailure` in `packages/shared/src/types.ts`.
    """

    url: str
    reason: str


class BulkImportResult(BaseModel):
    """Response body for `POST /feeds/bulk`.

    Always returned with HTTP 200 on shape-valid input; per-item failures
    land in `failed` rather than failing the batch (ADR-024 §24.2).
    Mirrors the TS `BulkImportResult` in `packages/shared/src/types.ts`.
    """

    created: int = Field(..., ge=0, description="New Feed rows created in this call.")
    skipped_duplicates: int = Field(
        ...,
        ge=0,
        description="URLs in the request that already existed for this user.",
    )
    failed: list[BulkImportFailure] = Field(
        default_factory=list,
        description="Per-URL failures (parse error, network error, DB error).",
    )
