"""Article scraper — newspaper3k + BeautifulSoup4 fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from newspaper import Article as NewspaperArticle

logger = logging.getLogger(__name__)

from api.services.ssrf_guard import (
    REDIRECT_CAP_HTTPCLIENT,
    SSRFGuardTransport,
    validate_outbound_url_async,
)


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
        # Per ADR-025 §5 (Task #70 follow-up): redirects are OFF by default.
        # Callers that need them can pass ``allow_redirects=True`` — the
        # transport re-validates every hop, and httpx's ``max_redirects``
        # provides a second-tier cap. The default of ``False`` matches the
        # test contract in ``test_scrape_uses_follow_redirects_false_default``
        # and reduces SSRF surface by default.
        self.allow_redirects = allow_redirects
        # One transport instance per scraper (re-uses httpx's connection
        # pool via the wrapped ``AsyncHTTPTransport``). The guard is
        # stateless across requests — the redirect counter is per-instance,
        # which matches httpx's own per-client counter semantics.
        self._transport = SSRFGuardTransport()

    async def scrape(self, url: str) -> ScrapedArticle:
        """Scrape a single URL. Returns a ScrapedArticle. Raises on fatal failures.

        Raises:
            SSRFError: if ``url`` targets a private/loopback/link-local
                address (per ADR-025). The router catches this and
                converts it to a 400 problem+json via the ADR-010
                handler matrix — no per-route handler needed.
        """
        # SSRF guard runs at the service boundary (per ADR-025 §1).
        # The transport ALSO re-runs this on every redirect hop.
        # Raised error propagates to the router / global handler.
        await validate_outbound_url_async(url)

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
            logger.debug(
                "newspaper3k parse failed, falling through to BS4", exc_info=True
            )

        # BS4 fallback — minimal extraction
        import httpx

        # Per Task #70: redirects stay ON by default; the transport
        # re-validates every hop. ``max_redirects`` is the second-tier
        # cap (httpx raises ``TooManyRedirects`` past the cap).
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=self.allow_redirects,
            max_redirects=REDIRECT_CAP_HTTPCLIENT,
            transport=self._transport,
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
