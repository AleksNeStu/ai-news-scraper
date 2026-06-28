"""Article scraper — newspaper3k + BeautifulSoup4 fallback."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from newspaper import Article as NewspaperArticle


@dataclass
class ScrapedArticle:
    url: str
    headline: str | None
    body: str | None
    source_domain: str | None
    publish_date: str | None
    authors: list[str]


class ArticleScraper:
    """Scrape any URL into a clean article. Two-tier: newspaper3k first, BS4 fallback."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def scrape(self, url: str) -> ScrapedArticle:
        """Scrape a single URL. Returns a ScrapedArticle. Raises on fatal failures."""

        # Try newspaper3k first
        try:
            article = NewspaperArticle(url, timeout=self.timeout)
            article.download()
            article.parse()
            if article.text and len(article.text) > 200:
                return ScrapedArticle(
                    url=url,
                    headline=article.title or None,
                    body=article.text,
                    source_domain=urlparse(url).netloc,
                    publish_date=article.publish_date.isoformat()
                    if article.publish_date
                    else None,
                    authors=article.authors or [],
                )
        except Exception:
            pass  # fall through to BS4

        # BS4 fallback — minimal extraction
        import httpx

        async with httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=True
        ) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()

        soup = BeautifulSoup(r.text, "lxml")
        # Heuristic: title tag, then largest <article>/<main>, fallback to <body>
        headline = (soup.title.string if soup.title else None) or None
        article_node = soup.find("article") or soup.find("main") or soup.body
        body = article_node.get_text(separator="\n", strip=True) if article_node else ""

        return ScrapedArticle(
            url=url,
            headline=headline,
            body=body or None,
            source_domain=urlparse(url).netloc,
            publish_date=None,
            authors=[],
        )
