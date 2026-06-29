"""Tests for the tiered curation scorer (Task #9, ADR-013).

Coverage:

* ``tier_from_score`` boundaries (ADR-013 §13.1, §13.12).
* ``_parse_score_response`` — extracts the first 0..1 float from
  free-text LLM output; returns ``None`` on parse failure or out-of-range.
* ``_is_stale`` — staleness against the 24h cache window.
* ``score_article`` fail-soft paths (ADR-013 §13.8):
    - placeholder / missing API key → ``(0.5, worth_a_look)``,
    - OpenAI exception → ``(0.5, worth_a_look)``,
    - parse failure → ``(0.5, worth_a_look)``,
    - valid response → ``(score, tier_from_score(score))``.

The LLM provider is monkeypatched so no real OpenAI call is made.
DB-dependent behaviour is covered in the future ``test_scorer_logging``
module (ADR-013 §13.13).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models.article import Article
from api.services.scorer import (
    DEFAULT_SCORE,
    _is_stale,
    _parse_score_response,
    score_article,
    tier_from_score,
)


# ---------------------------------------------------------------------------
# Tier boundaries — pure function, no DB / no LLM.
# ---------------------------------------------------------------------------


class TestTierFromScore:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (1.0, "must_read"),
            (0.85, "must_read"),
            (0.8499, "recommended"),
            (0.70, "recommended"),
            (0.6999, "worth_a_look"),
            (0.50, "worth_a_look"),
            (0.4999, "low_priority"),
            (0.0, "low_priority"),
        ],
    )
    def test_boundaries(self, score: float, expected: str) -> None:
        assert tier_from_score(score) == expected


# ---------------------------------------------------------------------------
# Score-response parser — pure function, no DB / no LLM.
# ---------------------------------------------------------------------------


class TestParseScoreResponse:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("0.85", 0.85),
            ("  0.7  ", 0.7),
            ("Score: 0.42", 0.42),
            ("1.0", 1.0),
            ("0", 0.0),
            ("1.5", None),  # out of range
            ("", None),
            ("abc", None),
        ],
    )
    def test_parse(self, raw: str, expected: float | None) -> None:
        assert _parse_score_response(raw) == expected


# ---------------------------------------------------------------------------
# Staleness — pure function, no DB / no LLM.
# ---------------------------------------------------------------------------


def _article(score: float | None, scored_at: datetime | None) -> Article:
    a = Article()
    a.score = score
    a.scored_at = scored_at
    a.headline = "test"
    return a


class TestIsStale:
    def test_none_scored_at_is_stale(self) -> None:
        now = datetime.now(timezone.utc)
        assert _is_stale(_article(None, None), now) is True

    def test_fresh_score_is_not_stale(self) -> None:
        now = datetime.now(timezone.utc)
        assert _is_stale(_article(0.5, now - timedelta(hours=1)), now) is False

    def test_old_score_is_stale(self) -> None:
        now = datetime.now(timezone.utc)
        assert _is_stale(_article(0.5, now - timedelta(hours=25)), now) is True


# ---------------------------------------------------------------------------
# score_article — fail-soft paths against the mock OpenAI client.
# ---------------------------------------------------------------------------


def _resp(text: str) -> MagicMock:
    """Shape of one ``chat.completions.create`` response (mirrors test_digest)."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    return response


class TestScoreArticleFailSoft:
    @pytest.mark.asyncio
    async def test_missing_key_returns_default(self) -> None:
        article = _article(None, None)
        with patch("api.services.scorer._settings") as mock_settings:
            mock_settings.openai_api_key = "sk-placeholder"
            score, tier = await score_article(None, article, None)
        assert score == DEFAULT_SCORE
        assert tier == "worth_a_look"

    @pytest.mark.asyncio
    async def test_openai_exception_returns_default(self) -> None:
        article = _article(None, None)
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")
        with patch("api.services.scorer._openai_client", return_value=mock_client):
            with patch("api.services.scorer._settings") as ms:
                ms.openai_api_key = "sk-real-key"
                score, tier = await score_article(None, article, None)
        assert score == DEFAULT_SCORE
        assert tier == "worth_a_look"

    @pytest.mark.asyncio
    async def test_parse_failure_returns_default(self) -> None:
        article = _article(None, None)
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _resp("this is not a number")
        with patch("api.services.scorer._openai_client", return_value=mock_client):
            with patch("api.services.scorer._settings") as ms:
                ms.openai_api_key = "sk-real-key"
                score, tier = await score_article(None, article, None)
        assert score == DEFAULT_SCORE
        assert tier == "worth_a_look"

    @pytest.mark.asyncio
    async def test_valid_response_returns_score_and_tier(self) -> None:
        article = _article(None, None)
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _resp("0.92")
        with patch("api.services.scorer._openai_client", return_value=mock_client):
            with patch("api.services.scorer._settings") as ms:
                ms.openai_api_key = "sk-real-key"
                score, tier = await score_article(None, article, None)
        assert score == 0.92
        assert tier == "must_read"
