"""Feeds router — RSS subscription management."""

import logging
from datetime import datetime, timezone
from uuid import UUID
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.deps import get_current_user_id
from api.models.feed import Feed
from api.models.feed_item import FeedItem
from api.schemas.feed import (
    BulkImportFailure,
    BulkImportRequest,
    BulkImportResult,
    FeedCreate,
    FeedItemOut,
    FeedListResponse,
    FeedOut,
    OpmlFeedRef,
)
from api.services.feed_parser import FeedParser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("", response_model=FeedListResponse)
async def list_feeds(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Feed, func.count(FeedItem.id).label("item_count"))
            .outerjoin(FeedItem, FeedItem.feed_id == Feed.id)
            .where(Feed.user_id == user_id)
            .group_by(Feed.id)
            .order_by(Feed.created_at.desc())
        )
    ).all()
    items = [
        FeedOut(
            id=f.id,
            feed_url=f.feed_url,
            title=f.title,
            description=f.description,
            last_polled=f.last_polled,
            active=f.active,
            item_count=ic,
            created_at=f.created_at,
        )
        for f, ic in rows
    ]
    return FeedListResponse(items=items, total=len(items))


@router.post("", response_model=FeedOut, status_code=status.HTTP_201_CREATED)
async def add_feed(
    payload: FeedCreate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Validate the feed URL by attempting a parse
    parser = FeedParser()
    parsed = parser.parse(str(payload.feed_url))
    if parsed is None:
        raise HTTPException(status_code=400, detail="Could not parse feed URL")

    feed = Feed(
        user_id=user_id,
        feed_url=str(payload.feed_url),
        title=parsed.title,
        description=parsed.description,
    )
    db.add(feed)
    await db.commit()
    await db.refresh(feed)

    return FeedOut(
        id=feed.id,
        feed_url=feed.feed_url,
        title=feed.title,
        description=feed.description,
        last_polled=feed.last_polled,
        active=feed.active,
        item_count=0,
        created_at=feed.created_at,
    )


@router.delete("/{feed_id}", status_code=204)
async def delete_feed(
    feed_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Feed).where(Feed.id == feed_id, Feed.user_id == user_id)
    )
    feed = res.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    await db.delete(feed)
    await db.commit()


@router.post("/bulk", response_model=BulkImportResult)
async def bulk_import_feeds(
    payload: BulkImportRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> BulkImportResult:
    """Bulk-import RSS feeds.

    Per Task #35 / ADR-024. Partial-success semantics: HTTP 200 with
    ``{created, skipped_duplicates, failed[]}``. Per-item failures do
    NOT fail the batch — invalid feeds land in ``failed`` with a
    reason, duplicates in the request body bump
    ``skipped_duplicates``, and races against another writer are
    caught via the existing ``(user_id, feed_url)`` UNIQUE constraint.
    """
    urls = [str(f.xml_url) for f in payload.feeds]

    # Observability breadcrumbs (Devil LOW-1): v1 keeps the parse step
    # synchronous, so a 500-item all-fail import can take ~4 minutes
    # and risk an upstream timeout. Log start/end for operator
    # correlation until the v2 job-queue path lands (ADR-024 §24.4).
    logger.info(
        "bulk_import started",
        extra={"user_id": str(user_id), "size": len(payload.feeds)},
    )

    # 1. Pre-fetch existing URLs in one query so we can skip them
    #    without round-tripping per item.
    existing_rows = await db.execute(
        select(Feed.feed_url).where(
            Feed.user_id == user_id,
            Feed.feed_url.in_(urls),
        )
    )
    existing = {row[0] for row in existing_rows.all()}

    # 2. Partition request into dup / new / intra-request-dup.
    seen_in_request: dict[str, None] = {}
    to_create: list[OpmlFeedRef] = []
    skipped_duplicates = 0
    failed: list[BulkImportFailure] = []

    for ref in payload.feeds:
        url_str = str(ref.xml_url)
        if url_str in existing:
            skipped_duplicates += 1
            continue
        if url_str in seen_in_request:
            failed.append(
                BulkImportFailure(url=url_str, reason="Duplicate URL in same request")
            )
            continue
        seen_in_request[url_str] = None
        to_create.append(ref)

    # 3. Parse + persist each new URL. Per-item failures (parse error,
    #    network error, race) never fail the batch.
    parser = FeedParser()
    created_count = 0

    for ref in to_create:
        url_str = str(ref.xml_url)
        # Devil LOW-2: FeedParser.parse already swallows network/parse
        # errors and returns None, so the prior bare `except Exception`
        # was masking programmer bugs (TypeError, AttributeError) as
        # "Could not parse feed". Rely on FeedParser as the error
        # boundary; let unexpected exceptions bubble to the 500 path
        # with a stack trace.
        parsed = parser.parse(url_str)
        if parsed is None:
            failed.append(BulkImportFailure(url=url_str, reason="Could not parse feed"))
            continue
        feed = Feed(
            user_id=user_id,
            feed_url=url_str,
            title=parsed.title,
            description=parsed.description,
            # Devil HIGH-1: `category` is accepted by OpmlFeedRef on the
            # wire (forward-compat with v2 category grouping) but
            # intentionally dropped here — Feed has no `category` column
            # yet (ADR-024 §24.2). Do NOT assign ref.category below
            # without first adding the column.
        )
        try:
            db.add(feed)
            await db.flush()
            created_count += 1
        except IntegrityError:
            # Race: another request inserted the same URL between our
            # SELECT and INSERT. Roll back this row only — keep the
            # outer transaction alive for the rest of the batch. Devil
            # LOW-3: expire the failed instance so it doesn't linger in
            # the session's identity map across the rest of the batch.
            await db.rollback()
            await db.expire(feed)
            skipped_duplicates += 1

    await db.commit()

    logger.info(
        "bulk_import finished",
        extra={
            "user_id": str(user_id),
            "created": created_count,
            "skipped_duplicates": skipped_duplicates,
            "failed_count": len(failed),
        },
    )

    return BulkImportResult(
        created=created_count,
        skipped_duplicates=skipped_duplicates,
        failed=failed,
    )


@router.post("/{feed_id}/poll", response_model=list[FeedItemOut])
async def poll_feed(
    feed_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a poll of a single feed. Returns the new items found."""
    from datetime import datetime, timezone

    res = await db.execute(
        select(Feed).where(Feed.id == feed_id, Feed.user_id == user_id)
    )
    feed = res.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")

    parser = FeedParser()
    parsed = parser.parse(feed.feed_url)
    if parsed is None:
        raise HTTPException(status_code=502, detail="Feed parse failed")

    new_items: list[FeedItemOut] = []
    for item in parsed.items:
        # dedupe by (feed_id, guid)
        existing = await db.execute(
            select(FeedItem).where(
                FeedItem.feed_id == feed.id, FeedItem.guid == item.guid
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        fi = FeedItem(feed_id=feed.id, guid=item.guid, title=item.title, url=item.url)
        db.add(fi)
        await db.flush()
        new_items.append(
            FeedItemOut(
                id=fi.id,
                feed_id=fi.feed_id,
                article_id=fi.article_id,
                guid=fi.guid,
                title=fi.title,
                url=fi.url,
                fetched_at=fi.fetched_at,
            )
        )
    feed.last_polled = datetime.now(timezone.utc)
    await db.commit()
    return new_items


@router.get("/export", response_class=Response)
async def export_opml(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Export user's subscribed feeds as OPML 2.0 XML file (Task #10).

    Generates an OPML file containing all active feeds for download.
    Response includes Content-Disposition header for file download.
    """
    # Fetch all active feeds for this user
    res = await db.execute(
        select(Feed)
        .where(Feed.user_id == user_id, Feed.active)
        .order_by(Feed.created_at.asc())
    )
    feeds = res.scalars().all()

    # Build OPML XML structure
    # Root: <opml version="2.0">
    opml = Element("opml")
    opml.set("version", "2.0")
    opml.set("xmlns", "http://opml.org/spec2/opml-2.0.xml")

    # Head section
    head = SubElement(opml, "head")
    SubElement(head, "title").text = "ai-news-scraper Feeds"
    SubElement(head, "dateCreated").text = datetime.now(timezone.utc).isoformat()
    SubElement(head, "docs").text = "http://opml.org/spec2/opml-2.0.xml"

    # Body section with feed outlines
    body = SubElement(opml, "body")
    for feed in feeds:
        outline = SubElement(body, "outline")
        outline.set("type", "rss")
        outline.set("text", feed.title or "Untitled")
        outline.set("title", feed.title or "Untitled")
        outline.set("xmlUrl", feed.feed_url)
        if feed.description:
            outline.set("description", feed.description)

    # Serialize to XML string with declaration
    xml_bytes = tostring(opml, encoding="utf-8", xml_declaration=True)

    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={
            "Content-Disposition": ('attachment; filename="ai-news-scraper-feeds.opml"')
        },
    )
