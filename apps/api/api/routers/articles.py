"""Articles router — list + detail."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.deps import get_current_user_id
from api.models.article import Article
from api.schemas.article import ArticleListResponse, ArticleOut

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=ArticleListResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: str | None = None,
    topic: str | None = None,
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
    stmt = stmt.order_by(Article.indexed_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
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