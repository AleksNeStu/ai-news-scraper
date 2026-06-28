"""Article embedder — OpenAI text-embedding-3-small primary, sentence-transformers offline fallback."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ArticleEmbedder:
    """Generate vector embeddings for text."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    async def embed(self, text: str) -> list[float] | None:
        """Return a list[float] embedding, or None on failure."""
        if not text or len(text) < 10:
            return None
        try:
            resp = await self.client.embeddings.create(
                model=self.model,
                input=text[:8000],  # safe truncation
                dimensions=self.dimensions,
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            return None