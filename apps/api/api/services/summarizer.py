"""Article summarizer — delegates to the active LLM provider.

Per ADR-011 §11.8. The provider (and through it, the chat model) is
selected by the factory in ``services/llm``; this service holds no
SDK clients of its own.
"""

from __future__ import annotations

import logging

from api.services.llm import get_llm_provider

logger = logging.getLogger(__name__)


class ArticleSummarizer:
    """Generate 100–300 word summaries."""

    SYSTEM_PROMPT = (
        "You are a news editor. Given a full news article, write a tight 100–300 word "
        "summary that captures the key facts, named entities, and implications. "
        "Be neutral, precise, and avoid editorializing."
    )

    def __init__(self) -> None:
        # No api_key/model — those live on the provider selected by the factory.
        pass

    async def summarize(self, text: str) -> str | None:
        """Return a summary, or None if generation fails."""
        if not text or len(text) < 200:
            return None
        try:
            provider = get_llm_provider()
            result = await provider.chat(
                [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Summarize:\n\n{text[:12000]}"},
                ],
                max_tokens=600,
                temperature=0.2,
            )
            return result.strip()
        except Exception as e:
            logger.warning("Summarization failed: %s", e)
            return None
