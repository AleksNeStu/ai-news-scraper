"""Unauthenticated ``GET /s/{token}`` router (Task #33 / ADR-021).

Public, read-only projection of an article snapshot. The token IS the
credential — there is no second factor. The response is an explicit
allow-list of fields (see :class:`api.schemas.share.SharedArticleView`)
and never includes owner, library, raw body, embedding, or metadata.

Failure modes (ADR-021 §21.7):
* unknown token → ``404 share_not_found``
* expired token → ``410 Gone share_expired``

The response sets ``Cache-Control: private, max-age=0`` and
``X-Robots-Tag: noindex`` on every successful read (ADR-021 §21.4) so
shared caches never hold it and compliant crawlers do not index it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.exceptions import AppException
from api.middleware.rate_limit import rate_limit_ip
from api.schemas.share import SharedArticleView
from api.services.shared_links import (
    ShareExpired,
    ShareNotFound,
    record_visit,
    resolve_share,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["share"])


# --- AppException subclasses for 404/410 with custom error_code ----------
# ADR-021 §21.7 requires the response body to carry a machine-readable
# ``code`` that the front-end can switch on without parsing prose. The
# global AppException handler in ``api/main.py`` already serialises
# ``error_code`` into the body, so subclassing is the cheapest way to
# surface the project-specific code without forking the exception
# helper.
#
# Defined at module level so they are importable from tests and can be
# matched with ``pytest.raises(ShareNotFoundError)`` if needed.


class ShareNotFoundError(AppException):
    """HTTP 404 with ``error_code = "share_not_found"``."""

    status_code = 404
    error_code = "share_not_found"
    title = "Share link not found"


class ShareGoneError(AppException):
    """HTTP 410 with ``error_code = "share_expired"``."""

    status_code = 410
    error_code = "share_expired"
    title = "Share link expired"


# --- Cache + robots headers per ADR-021 §21.4 --------------------------------

_CACHE_HEADERS: dict[str, str] = {
    "Cache-Control": "private, max-age=0",
    "X-Robots-Tag": "noindex",
}


def _to_view_payload(
    article_payload: dict[str, Any],
    shared_at,
    expires_at,
) -> dict[str, Any]:
    """Build the explicit allow-list response body.

    Pulling from a plain dict and re-validating against
    ``SharedArticleView`` ensures any leaked column on the underlying
    ``Article`` row fails validation loudly — the allow-list IS the
    contract (ADR-021 §21.3).
    """
    return {
        "article_id": article_payload["article_id"],
        "title": article_payload["title"],
        "summary": article_payload["summary"],
        # Topics: deduped + sorted at the source so the response is
        # byte-stable across calls (ADR-021 §21.3).
        "topics": sorted(set(article_payload["topics"] or [])),
        "source_url": article_payload["source_url"],
        "published_at": article_payload["published_at"],
        "shared_at": shared_at,
        "expires_at": expires_at,
    }


@router.get(
    "/s/{token}",
    response_model=SharedArticleView,
    summary="Resolve a shareable article link (no auth, token is the credential).",
    responses={
        404: {"description": "Unknown or revoked share token."},
        410: {"description": "Share link has expired."},
    },
)
async def get_shared_article(
    token: str,
    # Defense-in-depth rate limit: 30 token resolutions per IP per
    # minute. Token entropy is the primary defense (258 bits); the
    # bucket exists to back-pressure brute-force scan attempts on
    # the public surface (Task #65 — Devil F2 follow-up from
    # Task #33). IP-based because the route is unauthenticated.
    _rl: Annotated[None, Depends(rate_limit_ip("share_public", limit=30, window_s=60))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Resolve a token to the public article projection.

    On miss returns 404 ``share_not_found``; on expiry returns
    ``410 Gone share_expired`` so compliant crawlers evict the URL
    (ADR-021 §21.7). The visit audit row is recorded AFTER the
    response body is built so concurrent GETs each register their
    presence in the same per-second bucket.
    """
    try:
        resolved = await resolve_share(db, token)
    except ShareNotFound:
        raise ShareNotFoundError(detail="Share link not found")
    except ShareExpired:
        raise ShareGoneError(detail="This share link has expired")

    article = resolved.article

    # Build the explicit allow-list payload BEFORE calling
    # ``record_visit`` so the audit insert + count are the only side
    # effects on the request path (ADR-021 §21.6).
    payload = _to_view_payload(
        {
            "article_id": article.id,
            "title": article.headline,
            "summary": article.summary,
            "topics": list(article.topics or []),
            "source_url": article.url,
            "published_at": article.publish_date,
        },
        shared_at=resolved.shared_at,
        expires_at=resolved.expires_at,
    )

    # Validate against the schema BEFORE serialising so any leaked
    # field on the underlying row fails loudly — this is the
    # allow-list contract (ADR-021 §21.3).
    view = SharedArticleView.model_validate(payload)

    # Audit insert + count (ADR-021 §21.6). Best-effort — a failure
    # here MUST NOT block the response (the visitor is entitled to
    # the page; visit accounting is auxiliary).
    try:
        await record_visit(db, resolved.shared_link_id)
    except Exception:
        logger.warning(
            "visit audit failed for shared_link_id=%s (non-blocking)",
            resolved.shared_link_id,
            exc_info=True,
        )

    return JSONResponse(
        content=view.model_dump(mode="json"),
        headers=_CACHE_HEADERS,
    )


__all__ = ["ShareGoneError", "ShareNotFoundError", "router"]
