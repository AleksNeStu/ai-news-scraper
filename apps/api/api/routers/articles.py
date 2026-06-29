"""Articles router — list + detail."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import AsyncSessionLocal, get_db
from api.deps import get_current_user_id
from api.models.article import Article
from api.schemas.article import ArticleListResponse, ArticleOut, TierLiteral
from api.services.scorer import ensure_fresh_scores

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=ArticleListResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: str | None = None,
    topic: str | None = None,
    # Task #9 / ADR-013 §13.2 — tier filter + group-by-tier ordering.
    # When ``group_by_tier=true`` the response is still a flat list but
    # ordered by (tier, score DESC NULLS LAST, indexed_at DESC) so the
    # front-end can render four sections from one fetch.
    tier: TierLiteral | None = None,
    group_by_tier: bool = False,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Article).where(Article.user_id == user_id)
    count_stmt = select(func.count(Article.id)).where(Article.user_id == user_id)
    if source:
        stmt = stmt.where(Article.source_domain == source)
        count_stmt = count_stmt.where(Article.source_domain == source)
    if topic:
        stmt = stmt.where(Article.topics.any(topic))
        count_stmt = count_stmt.where(Article.topics.any(topic))
    if tier:
        stmt = stmt.where(Article.tier == tier)
        count_stmt = count_stmt.where(Article.tier == tier)
    if group_by_tier:
        # ADR-013 §13.2 — tier-grouped ordering. The composite index
        # ``ix_articles_tier_scored_at`` covers tier filtering and the
        # leading ``tier`` column here; ``score`` and ``indexed_at`` are
        # in-memory sorts (page_size is capped at 100).
        # NULLS LAST keeps never-scored articles at the bottom of each
        # tier bucket so freshly-ingested content doesn't punch above
        # its weight.
        stmt = stmt.order_by(
            Article.tier.asc().nulls_last(),
            Article.score.desc().nulls_last(),
            Article.indexed_at.desc(),
        )
    else:
        stmt = stmt.order_by(Article.indexed_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    # ADR-013 §13.11 — lazy trigger. The HTTP handler returns
    # immediately; per-article background tasks fill the cache while
    # the user is reading. The session_factory parameter is REQUIRED
    # for background scoring; without it ``ensure_fresh_scores`` is a
    # no-op (no LLM cost, no latency — but also no fresh scores until
    # the next read).
    await ensure_fresh_scores(db, items, user=None, session_factory=AsyncSessionLocal)
    return ArticleListResponse(
        items=[ArticleOut.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == user_id)
    )
    article = res.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    # ADR-013 §13.2 — single-article view gets the same lazy scoring
    # trigger as the list endpoint.
    await ensure_fresh_scores(
        db, [article], user=None, session_factory=AsyncSessionLocal
    )
    return ArticleOut.model_validate(article)


@router.delete("/{article_id}", status_code=204)
async def delete_article(
    article_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == user_id)
    )
    article = res.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    await db.delete(article)
    await db.commit()
