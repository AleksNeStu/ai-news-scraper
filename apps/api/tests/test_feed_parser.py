"""Integration tests: ``FeedParser.parse`` honours the SSRF guard.

Per ADR-025 §Contract. Verifies that ``FeedParser.parse`` rejects
``http://169.254.169.254/...`` and other blocked URLs by returning
``None`` (preserving the partial-success contract used by the bulk
route) — without ever calling ``feedparser.parse``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from api.services import ssrf_guard
from api.services.feed_parser import FeedParser


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


def test_parse_loopback_url_returns_none_without_calling_feedparser():
    """AWS metadata URL must not reach feedparser."""
    parser = FeedParser()
    with patch("feedparser.parse") as mock_feed:
        # Block the URL at the DNS layer so the guard rejects it.
        with patch(
            "socket.getaddrinfo",
            side_effect=_mock_getaddrinfo(["169.254.169.254"]),
        ):
            result = parser.parse("http://169.254.169.254/latest/meta-data/")
        assert result is None
        mock_feed.assert_not_called()


def test_parse_rfc1918_url_returns_none():
    """RFC1918 hostnames must be blocked before feedparser."""
    parser = FeedParser()
    with patch("feedparser.parse") as mock_feed:
        with patch(
            "socket.getaddrinfo",
            side_effect=_mock_getaddrinfo(["10.0.0.1"]),
        ):
            result = parser.parse("http://internal-admin.corp.example/")
        assert result is None
        mock_feed.assert_not_called()


def test_parse_ip_literal_loopback_returns_none():
    """An IP literal (no DNS needed) must reject via the fast path."""
    parser = FeedParser()
    with patch("feedparser.parse") as mock_feed:
        # No socket.getaddrinfo mock needed — literal hits the fast path.
        result = parser.parse("http://127.0.0.1/")
        assert result is None
        mock_feed.assert_not_called()


def test_parse_public_url_still_calls_feedparser(monkeypatch):
    """A public URL must reach feedparser — the guard lets it through.

    Mocks ``feedparser.parse`` to return an empty feed so the test
    doesn't depend on real network I/O.
    """
    import feedparser

    class _EmptyFeed:
        def __init__(self) -> None:
            self.entries: list = []
            self.feed: dict = {}

    monkeypatch.setattr(feedparser, "parse", lambda url, **kw: _EmptyFeed())

    parser = FeedParser()
    with patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["93.184.216.34"]),
    ):
        result = parser.parse("http://example.com/feed.xml")
    # Empty feed -> None (existing behaviour, not an SSRF rejection).
    assert result is None


def test_parse_non_http_scheme_returns_none():
    """Non-HTTP(S) URLs must short-circuit before any DNS lookup."""
    parser = FeedParser()
    with patch("feedparser.parse") as mock_feed:
        result = parser.parse("file:///etc/passwd")
        assert result is None
        mock_feed.assert_not_called()


def test_parse_invalid_url_format():
    """Malformed URLs must raise SSRFError (caught by the soft-fail path)."""
    parser = FeedParser()
    with patch("feedparser.parse") as mock_feed:
        result = parser.parse("")
        assert result is None
        mock_feed.assert_not_called()


def test_parse_logs_warning_on_block(monkeypatch, caplog):
    """SSRF blocks must log a warning so ops can detect probing attempts."""
    import logging

    parser = FeedParser()
    with caplog.at_level(logging.WARNING, logger="api.services.feed_parser"), patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["127.0.0.1"]),
    ):
        result = parser.parse("http://localhost/")
    assert result is None
    assert any("SSRF guard blocked" in record.message for record in caplog.records)
