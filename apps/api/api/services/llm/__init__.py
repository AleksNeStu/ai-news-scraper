"""LLM provider factory and selection.

Per ADR-011 §11.4. Selection is driven by the ``LLM_PROVIDER`` env var
(default: ``deepseek``). Each provider is constructed with the matching
env-var-stored API key.
"""

from __future__ import annotations

from api.config import get_settings
from .base import LLMProvider
from .deepseek import DeepSeekProvider
from .gemini import GeminiProvider
from .openrouter import OpenRouterProvider


def get_llm_provider() -> LLMProvider:
    """Select provider via LLM_PROVIDER env var. Default: deepseek."""
    s = get_settings()
    name = (s.llm_provider or "deepseek").lower()
    if name == "deepseek":
        return DeepSeekProvider(api_key=s.deepseek_api_key)
    if name == "gemini":
        return GeminiProvider(api_key=s.gemini_api_key or s.google_api_key)
    if name == "openrouter":
        return OpenRouterProvider(api_key=s.openrouter_api_key)
    raise ValueError(f"Unknown LLM_PROVIDER: {name!r}")


__all__ = ["LLMProvider", "get_llm_provider"]
