"""LLMProvider protocol — the pluggable chat + embed contract.

Per ADR-011 §11.1. Concrete providers live in ``deepseek.py``,
``openrouter.py``, and ``gemini.py``; the factory in ``__init__.py``
selects one based on the ``LLM_PROVIDER`` env var.
"""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """Pluggable chat + embed. Implementations: deepseek, gemini, openrouter."""

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        **kw,
    ) -> str: ...

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]: ...
