"""Authenticated ``POST /share`` router (Task #33 / ADR-021).

Mints a fresh public-shareable URL for an article owned by the caller.
The endpoint is authenticated via the standard ``get_current_user_id``
dependency (same posture as ``/articles``). The unauthenticated read
endpoint lives at :mod:`api.routers.public`.

Why the URL is built server-side: ``request.base_url`` keeps the path
portable across reverse proxies, alternate hosts (preview / staging /
production), and trailing-slash environments (ADR-021 §21.2). The
client MUST NOT compose the URL — relying on the server-built URL
guarantees the host and scheme are exactly what the API is listening
on.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.deps import get_current_user_id
from api.middleware.rate_limit import rate_limit_user
from api.schemas.share import ShareCreateRequest, ShareResponse
from api.services.shared_links import mint_share

router = APIRouter(tags=["share"])


@router.post(
    "/share",
    response_model=ShareResponse,
    status_code=201,
    summary="Mint a public shareable URL for an article you own.",
)
async def create_share(
    payload: ShareCreateRequest,
    request: Request,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShareResponse:
    """Mint a fresh share token and return a server-built URL.

    The returned ``token`` is the ONLY place the raw token survives.
    The DB stores only ``sha256(token)`` — a DB leak does not yield
    working URLs (ADR-021 §21.1, §21.9).
    """
    # Defense-in-depth rate limit: 20 share creations per user per hour.
    # Token entropy (258 bits via secrets.token_urlsafe(32)) is the
    # primary defense, but the bucket protects the article-ownership
    # SQL lookup + sha256 write from accidental abuse (Task #65 —
    # Devil F2 follow-up from Task #33).
    await rate_limit_user("share_create", user_id, limit=20, window_s=3600)

    minted = await mint_share(
        db,
        user_id=user_id,
        article_id=payload.article_id,
        ttl_days=payload.ttl_days,
    )

    # ``request.base_url`` already includes the trailing slash; the
    # rstrip guarantees the URL is exactly ``<origin>/s/<token>``.
    base = str(request.base_url).rstrip("/")
    url = f"{base}/s/{minted.token}"

    return ShareResponse(
        token=minted.token,
        url=url,
        expires_at=minted.expires_at,
        article_id=payload.article_id,
    )


__all__ = ["router"]
