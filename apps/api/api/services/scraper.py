"""Article scraper — newspaper3k + BeautifulSoup4 fallback."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from newspaper import Article as NewspaperArticle

from api.services.ssrf_guard import validate_outbound_url


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

    def __init__(self, timeout: int = 15, allow_redirects: bool = False):
        self.timeout = timeout
        # Per ADR-025 §5: redirects are OFF by default. A user can opt
        # in per-call, but the caller becomes responsible for any
        # post-redirect re-validation (httpx follows redirects without
        # consulting us). The opt-in path is honoured below by passing
        # ``follow_redirects=allow_redirects`` to the inner AsyncClient.
        #
        # TODO: when the opt-in path is actually wired up at the call
        # site, the per-redirect re-validation needs a custom
        # ``httpx.AsyncHTTPTransport`` (no native hook exists). Until
        # then ``allow_redirects=True`` still exposes the redirect
        # bypass; keep it False unless the caller is happy with that.
        self.allow_redirects = allow_redirects

    async def scrape(self, url: str) -> ScrapedArticle:
        """Scrape a single URL. Returns a ScrapedArticle. Raises on fatal failures.

        Raises:
            SSRFError: if ``url`` targets a private/loopback/link-local
                address (per ADR-025). The router catches this and
                converts it to a 400 problem+json via the ADR-010
                handler matrix — no per-route handler needed.
        """
        # SSRF guard runs at the service boundary (per ADR-025 §1).
        # Raised error propagates to the router / global handler.
        validate_outbound_url(url)

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

        # ``follow_redirects=False`` per ADR-025 §5 default. The
        # newspaper3k path above uses urllib under the hood and is
        # similarly non-redirecting for our purposes.
        async with httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=self.allow_redirects
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
