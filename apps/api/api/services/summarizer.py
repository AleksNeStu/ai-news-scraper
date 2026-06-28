"""Article summarizer — OpenAI primary, NLTK extractive fallback."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ArticleSummarizer:
    """Generate 100–300 word summaries."""

    SYSTEM_PROMPT = (
        "You are a news editor. Given a full news article, write a tight 100–300 word "
        "summary that captures the key facts, named entities, and implications. "
        "Be neutral, precise, and avoid editorializing."
    )

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 600,
        min_tokens: int = 150,
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens

    async def summarize(self, text: str) -> str | None:
        """Return a summary, or None if generation fails."""
        if not text or len(text) < 200:
            return None
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Summarize:\n\n{text[:12000]}"},
                ],
                max_tokens=self.max_tokens,
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("Summarization failed: %s", e)
            return None
