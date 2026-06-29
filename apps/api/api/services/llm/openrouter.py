"""OpenRouter provider — gateway fallback.

Per ADR-011 §11.3. Acts as gateway-of-last-resort when direct providers
are unconfigured, rate-limited, or unavailable. Speaks OpenAI shape.
"""

from __future__ import annotations

from ._openai_compat import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_CHAT_MODEL = (
        "openai/gpt-4o-mini"  # sensible default; override via LLM_MODEL
    )
    DEFAULT_EMBED_MODEL = "openai/text-embedding-3-small"
