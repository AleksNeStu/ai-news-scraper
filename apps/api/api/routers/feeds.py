"""Feeds router — RSS subscription management."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.deps import get_current_user_id
from api.models.feed import Feed
from api.models.feed_item import FeedItem
from api.schemas.feed import FeedCreate, FeedItemOut, FeedListResponse, FeedOut
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
            select(FeedItem).where(FeedItem.feed_id == feed.id, FeedItem.guid == item.guid)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        fi = FeedItem(feed_id=feed.id, guid=item.guid, title=item.title, url=item.url)
        db.add(fi)
        await db.flush()
        new_items.append(
            FeedItemOut(
                id=fi.id, feed_id=fi.feed_id, article_id=fi.article_id,
                guid=fi.guid, title=fi.title, url=fi.url, fetched_at=fi.fetched_at,
            )
        )
    feed.last_polled = datetime.now(timezone.utc)
    await db.commit()
    return new_items