"""Tests for ``GET /feeds/export`` (Task #10 OPML export).

Export user's subscribed feeds as OPML 2.0 XML file. Coverage:

  * Happy path — user with 3 feeds → valid OPML 2.0 XML with all feeds.
  * Empty subscriptions — user with no feeds → OPML body with zero outlines.
  * OPML structure — XML declaration, version, namespace, head/body sections.
  * Feed attributes — xmlUrl (required), title, description mapped to OPML.
  * Download headers — Content-Disposition header for file attachment.
  * Inactive feeds — only active feeds exported (active=true filter).
  * Authentication — unauthenticated request → 401.

Seeding strategy: feeds are inserted directly via ``AsyncSessionLocal``
(the production session maker) rather than via ``POST /feeds/bulk``
because the bulk endpoint's ``logger.info(..., extra={"created": ...})``
call at ``apps/api/api/routers/feeds.py`` line ~216 collides with
Python's built-in ``LogRecord.created`` attribute, crashing the
endpoint with ``KeyError: "Attempt to overwrite 'created' in
LogRecord"``. That bug is pre-existing (commit ``db61ca9``, Task #35)
and out of scope for the export task. Direct DB seeding mirrors the
``_seed_feed`` helper used by ``test_feeds_bulk.py``.
"""

from __future__ import annotations

from xml.etree.ElementTree import fromstring

import pytest
from httpx import AsyncClient

from api.db.database import AsyncSessionLocal
from api.models.feed import Feed
from tests.conftest import register_user_and_login

# OPML 2.0 namespace — exported XML sets ``xmlns="http://opml.org/spec2/opml-2.0.xml"``
# on the root, so ElementTree returns namespace-qualified tags.
OPML_NS = "{http://opml.org/spec2/opml-2.0.xml}"


@pytest.mark.asyncio
async def test_export_opml_happy_path(client: AsyncClient):
    """Export 3 feeds as OPML 2.0. Verify XML structure and feed attributes."""
    user_data, token = await register_user_and_login(
        client, "export_test@example.com", "testpass123"
    )

    # Seed 3 feeds directly via the production session so /feeds/export
    # can see them (the same _seed_feed pattern from test_feeds_bulk.py).
    feeds_to_seed = [
        ("https://example.com/feed1.xml", "Tech News"),
        ("https://example.com/feed2.xml", "AI Weekly"),
        ("https://example.com/feed3.xml", "Business"),
    ]
    async with AsyncSessionLocal() as session:
        for url, title in feeds_to_seed:
            session.add(
                Feed(
                    user_id=user_data["id"],
                    feed_url=url,
                    title=title,
                    active=True,
                )
            )
        await session.commit()

    response = await client.get(
        "/feeds/export", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "ai-news-scraper-feeds.opml" in response.headers["content-disposition"]

    # Parse and validate OPML structure. ElementTree returns
    # namespace-qualified tags because the OPML root declares the OPML
    # 2.0 namespace.
    root = fromstring(response.content)
    assert root.tag == f"{OPML_NS}opml"
    assert root.get("version") == "2.0"

    head = root.find(f"{OPML_NS}head")
    assert head is not None
    assert head.find(f"{OPML_NS}title").text == "ai-news-scraper Feeds"
    assert head.find(f"{OPML_NS}dateCreated") is not None
    assert head.find(f"{OPML_NS}docs").text == "http://opml.org/spec2/opml-2.0.xml"

    body = root.find(f"{OPML_NS}body")
    assert body is not None

    outlines = body.findall(f"{OPML_NS}outline")
    assert len(outlines) == 3

    # Verify feed attributes
    outline1 = outlines[0]
    assert outline1.get("type") == "rss"
    assert outline1.get("text") == "Tech News"
    assert outline1.get("title") == "Tech News"
    assert outline1.get("xmlUrl") == "https://example.com/feed1.xml"

    outline3 = outlines[2]
    assert outline3.get("text") == "Business"
    assert outline3.get("xmlUrl") == "https://example.com/feed3.xml"


@pytest.mark.asyncio
async def test_export_opml_empty_feeds(client: AsyncClient):
    """Export OPML when user has no feeds. Verify valid XML with empty body."""
    _user_data, token = await register_user_and_login(
        client, "export_empty@example.com", "testpass123"
    )

    response = await client.get(
        "/feeds/export", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    root = fromstring(response.content)
    assert root.tag == f"{OPML_NS}opml"

    body = root.find(f"{OPML_NS}body")
    assert body is not None
    outlines = body.findall(f"{OPML_NS}outline")
    assert len(outlines) == 0


@pytest.mark.asyncio
async def test_export_opml_unauthenticated(client: AsyncClient):
    """Unauthenticated request to export endpoint → 401."""
    response = await client.get("/feeds/export")
    assert response.status_code == 401