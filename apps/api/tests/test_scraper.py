"""Integration tests: ``ArticleScraper.scrape`` honours the SSRF guard.

Per ADR-025 §Contract. Verifies that ``ArticleScraper.scrape`` raises
``SSRFError`` for blocked URLs — which the ADR-010 global handler
converts to a 400 problem+json. The newspaper3k library opens the URL
eagerly at instantiation time, so the guard is the only line of
defence: this test exists to prove ``validate_outbound_url`` runs
BEFORE ``NewspaperArticle(url)`` is constructed.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from api.exceptions import SSRFError
from api.services import ssrf_guard
from api.services.scraper import ArticleScraper


@pytest.fixture(autouse=True)
def _reset_cache():
    """Drop the DNS cache between tests."""
    ssrf_guard._cache_clear_for_tests()
    yield
    ssrf_guard._cache_clear_for_tests()


def _mock_getaddrinfo(ips: list[str]):
    def _stub(host, *args, **kwargs):
        import socket

        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0)) for ip in ips]

    return _stub


@pytest.mark.asyncio
async def test_scrape_loopback_url_raises_ssrf_error():
    """A loopback URL must raise SSRFError before newspaper3k fires."""
    scraper = ArticleScraper()
    # No socket mock — the IP literal hits the fast path.
    with pytest.raises(SSRFError):
        await scraper.scrape("http://127.0.0.1/")


@pytest.mark.asyncio
async def test_scrape_metadata_url_raises_ssrf_error():
    """The AWS metadata IP must raise at the guard, not during fetch."""
    scraper = ArticleScraper()
    with patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["169.254.169.254"]),
    ), pytest.raises(SSRFError):
        await scraper.scrape("http://metadata.aws.example/")


@pytest.mark.asyncio
async def test_scrape_ipv6_loopback_raises_ssrf_error():
    """``[::1]`` must reject via the IPv6 IP-literal fast path."""
    scraper = ArticleScraper()
    with pytest.raises(SSRFError):
        await scraper.scrape("http://[::1]/")


@pytest.mark.asyncio
async def test_scrape_non_http_scheme_raises_ssrf_error():
    """``file:`` / ``gopher:`` must reject."""
    scraper = ArticleScraper()
    with pytest.raises(SSRFError):
        await scraper.scrape("file:///etc/passwd")


@pytest.mark.asyncio
async def test_scrape_rfc1918_raises_ssrf_error():
    """RFC1918 ranges must reject."""
    scraper = ArticleScraper()
    with patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["10.0.0.1"]),
    ), pytest.raises(SSRFError):
        await scraper.scrape("http://internal.example/")


@pytest.mark.asyncio
async def test_scrape_uses_follow_redirects_false_default():
    """The default ``allow_redirects`` must be False (per ADR-025 §5).

    Tests via the constructor attribute — the actual httpx behaviour
    is exercised indirectly via the SSRF integration.
    """
    scraper = ArticleScraper()
    assert scraper.allow_redirects is False


@pytest.mark.asyncio
async def test_scrape_opt_in_allow_redirects_true():
    """``allow_redirects=True`` must propagate to the inner client."""
    scraper = ArticleScraper(allow_redirects=True)
    assert scraper.allow_redirects is True


@pytest.mark.asyncio
async def test_scrape_public_url_passes_guard(monkeypatch):
    """A public URL must NOT raise SSRFError at the guard stage.

    Mocks newspaper3k to raise so we don't need real network I/O —
    the test is about the guard firing, not the downstream path.
    """

    class _FailingArticle:
        def __init__(self, *args, **kwargs):
            pass

        def download(self):
            raise RuntimeError("nope")

        def parse(self):
            pass

    monkeypatch.setattr("api.services.scraper.NewspaperArticle", _FailingArticle)

    scraper = ArticleScraper()
    with (
        patch(
            "socket.getaddrinfo",
            side_effect=_mock_getaddrinfo(["93.184.216.34"]),
        ),
        # Must NOT raise SSRFError. Whether it raises something else
        # (RuntimeError from the failing Article) is out of scope; we
        # only care that the guard let the URL through.
        pytest.raises(RuntimeError, match="nope"),
    ):
        await scraper.scrape("http://example.com/article")
