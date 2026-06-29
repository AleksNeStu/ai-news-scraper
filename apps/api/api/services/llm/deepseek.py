"""DeepSeek provider — direct, cheapest chat path.

Per ADR-011 §11.3. DeepSeek has no native embedding model, so
``embed()`` raises ``NotImplementedError``; callers needing embeddings
must route through OpenRouter instead.
"""

from __future__ import annotations

from ._openai_compat import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_CHAT_MODEL = "deepseek-chat"
    # DeepSeek has no native embed model; intentionally no DEFAULT_EMBED_MODEL.
    # ``embed()`` is overridden to refuse the call rather than hit the API.

    async def embed(self, texts, *, model=None):  # type: ignore[override]
        raise NotImplementedError(
            "DeepSeek has no native embedding model; route embeds via OpenRouter."
        )
