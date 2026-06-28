"""RSS feed parser — feedparser + scrape pipeline trigger."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import feedparser

from api.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


@dataclass
class ParsedFeedItem:
    guid: str
    title: str | None
    url: str | None
    summary: str | None
    published: str | None


@dataclass
class ParsedFeed:
    title: str | None
    description: str | None
    items: list[ParsedFeedItem]


class FeedParser:
    """Parse an RSS/Atom feed into structured form."""

    def __init__(self, user_agent: str | None = None, max_items: int | None = None):
        self.user_agent = user_agent or _settings.rss_user_agent
        self.max_items = max_items or _settings.rss_max_items_per_poll

    def parse(self, feed_url: str) -> ParsedFeed | None:
        """Return a ParsedFeed or None on error."""
        try:
            parsed = feedparser.parse(feed_url, agent=self.user_agent)
        except Exception as e:
            logger.warning("feedparser failed for %s: %s", feed_url, e)
            return None
        if not parsed or not parsed.entries:
            return None

        items: list[ParsedFeedItem] = []
        for entry in parsed.entries[: self.max_items]:
            items.append(
                ParsedFeedItem(
                    guid=entry.get("id") or entry.get("link") or entry.get("title", ""),
                    title=entry.get("title"),
                    url=entry.get("link"),
                    summary=entry.get("summary"),
                    published=entry.get("published"),
                )
            )

        return ParsedFeed(
            title=parsed.feed.get("title") if hasattr(parsed, "feed") else None,
            description=parsed.feed.get("description") if hasattr(parsed, "feed") else None,
            items=items,
        )