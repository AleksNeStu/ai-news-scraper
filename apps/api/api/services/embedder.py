"""Article embedder — delegates to the active LLM provider.

Per ADR-011 §11.8. Embedding model + dimension are decided by the
provider selected via ``services/llm``. ``embed()`` returns the first
vector from the provider's batched ``embed()`` to preserve the prior
single-vector contract used by routers.
"""

from __future__ import annotations

import logging

from api.services.llm import get_llm_provider

logger = logging.getLogger(__name__)


class ArticleEmbedder:
    """Generate a single vector embedding for text."""

    def __init__(self) -> None:
        # No api_key/model/dimensions — those live on the provider.
        pass

    async def embed(self, text: str) -> list[float] | None:
        """Return a list[float] embedding, or None on failure."""
        if not text or len(text) < 10:
            return None
        try:
            provider = get_llm_provider()
            vectors = await provider.embed([text[:8000]])
            if not vectors:
                return None
            return vectors[0]
        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            return None
