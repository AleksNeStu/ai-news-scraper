"""Public shareable article-link schemas.

Task #33 / ADR-021. ``POST /share`` mints an opaque, unguessable token and
returns a server-built URL; ``GET /s/{token}`` is the unauthenticated read
endpoint that serves ``SharedArticleView``.

The Pydantic models here mirror the TS types in
``packages/shared/src/types.ts`` (manual mirror — see the comment block at
the top of that file). Keep both in lock-step in the same commit or the
typecheck / pytest will fail on one side.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ShareCreateRequest(BaseModel):
    """Payload for ``POST /share``.

    ``ttl_days`` defaults to 30 and is capped at 365 to prevent the obvious
    DoS of a multi-decade token. The cap is enforced server-side; a client
    that sends ``ttl_days=10000`` receives a 422 (ADR-021 §21.8).
    """

    article_id: UUID
    ttl_days: int = Field(default=30, ge=1, le=365)


class ShareResponse(BaseModel):
    """Response body for ``POST /share``.

    ``url`` is built server-side from ``request.base_url`` + the freshly
    minted token. Clients MUST NOT compose the URL themselves — relying on
    a server-built URL keeps the share path portable across reverse
    proxies, alternate hosts, and trailing-slash environments (ADR-021
    §21.2).
    """

    token: str
    url: str
    expires_at: datetime
    article_id: UUID


class SharedArticleView(BaseModel):
    """Unauthenticated public projection of an article.

    Served by ``GET /s/{token}``. The field set is an explicit allow-list
    (ADR-021 §21.3) — every field not listed here is intentionally
    EXCLUDED. Anonymous visitors must not be able to:

      * learn who owns the article (``owner_id`` / ``user_id`` excluded),
      * pivot to the owner's other articles (no ``library_id`` /
        embedding / internal metadata),
      * read the full scrape body (``body`` / ``raw_content`` excluded),
      * enumerate owner tags or private notes (``metadata`` is excluded
        wholesale — only the curated ``topics`` list survives).

    ``topics`` is deduped and sorted at the service layer so the response
    is byte-stable across calls (simplifies client caching and test
    diffing). ``shared_at`` is when the share was created (NOT the visit
    time — visit time lives in the audit log, never in the response).
    """

    article_id: UUID
    title: str
    summary: str | None = None
    topics: list[str] = Field(default_factory=list)
    source_url: str | None = None
    published_at: datetime | None = None
    shared_at: datetime
    expires_at: datetime
