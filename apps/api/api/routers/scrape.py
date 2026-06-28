"""Scrape router — submit URL(s) for processing."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.db.database import get_db
from api.deps import get_current_user_id
from api.models.article import Article
from api.schemas.article import ArticleOut, BatchScrapeRequest, ScrapeRequest
from api.services.embedder import ArticleEmbedder
from api.services.scraper import ArticleScraper
from api.services.summarizer import ArticleSummarizer
from api.services.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scrape", tags=["scrape"])
_settings = get_settings()

# Service singletons (init in lifespan; reuse)
_scraper = ArticleScraper()
_summarizer = ArticleSummarizer(api_key=_settings.openai_api_key, model=_settings.openai_model)
_embedder = ArticleEmbedder(api_key=_settings.openai_api_key, model=_settings.openai_embedding_model, dimensions=_settings.embedding_dimensions)
_vector_store = ChromaVectorStore()


async def _process_one(url: str, user_id: UUID | None, db: AsyncSession) -> Article:
    """Scrape → summarize → embed → persist. Returns the Article row."""
    scraped = await _scraper.scrape(url)
    summary = None
    if scraped.body:
        summary = await _summarizer.summarize(scraped.body)
    embedding = None
    text_to_embed = (scraped.headline or "") + "\n\n" + (summary or scraped.body or "")
    if text_to_embed.strip():
        embedding = await _embedder.embed(text_to_embed)

    # Upsert article (dedup by (user_id, url))
    article = Article(
        user_id=user_id,
        url=url,
        headline=scraped.headline,
        body=scraped.body,
        summary=summary,
        topics=[],  # TODO: extract via TopicExtractor (P1)
        source_domain=scraped.source_domain,
        publish_date=scraped.publish_date,
    )
    stmt = pg_insert(Article).values(
        user_id=user_id,
        url=url,
        headline=scraped.headline,
        body=scraped.body,
        summary=summary,
        topics=[],
        source_domain=scraped.source_domain,
        publish_date=scraped.publish_date,
    ).on_conflict_do_update(
        index_elements=["user_id", "url"],
        set_={
            "headline": scraped.headline,
            "body": scraped.body,
            "summary": summary,
            "source_domain": scraped.source_domain,
            "publish_date": scraped.publish_date,
        },
    ).returning(Article)
    res = await db.execute(stmt)
    article = res.scalar_one()
    await db.commit()
    await db.refresh(article)

    # Index in ChromaDB
    if embedding is not None:
        try:
            await _vector_store.upsert(
                collection="articles",
                ids=[str(article.id)],
                embeddings=[embedding],
                documents=[text_to_embed],
                metadatas=[{"user_id": str(user_id) if user_id else "", "source_domain": scraped.source_domain or ""}],
            )
        except Exception as e:
            logger.warning("ChromaDB upsert failed (article saved in PG): %s", e)

    return article


@router.post("", response_model=ArticleOut, status_code=status.HTTP_201_CREATED)
async def scrape(
    payload: ScrapeRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    article = await _process_one(str(payload.url), user_id, db)
    return ArticleOut.model_validate(article)


@router.post("/batch", response_model=list[ArticleOut])
async def scrape_batch(
    payload: BatchScrapeRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    out: list[ArticleOut] = []
    for url in payload.urls:
        try:
            article = await _process_one(str(url), user_id, db)
            out.append(ArticleOut.model_validate(article))
        except Exception as e:
            logger.warning("Batch scrape failed for %s: %s", url, e)
    return out