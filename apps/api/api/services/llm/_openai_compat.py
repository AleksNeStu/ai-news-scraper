"""OpenAI-compatible provider base.

Per ADR-011 §11.2. Reuses the ``openai`` SDK (``AsyncOpenAI``) against
each vendor's OpenAI-shaped HTTP endpoint. Subclasses set
``DEFAULT_BASE_URL`` plus default chat/embed model names.
"""

from __future__ import annotations

from openai import AsyncOpenAI


class OpenAICompatibleProvider:
    """Base for providers that speak the OpenAI HTTP shape.

    Concrete subclasses (deepseek, openrouter) set ``DEFAULT_BASE_URL``,
    ``DEFAULT_CHAT_MODEL``, and (when they support embeddings)
    ``DEFAULT_EMBED_MODEL``.
    """

    DEFAULT_BASE_URL: str = ""
    DEFAULT_CHAT_MODEL: str = ""
    DEFAULT_EMBED_MODEL: str = ""

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    async def chat(
        self, messages: list[dict], *, model: str | None = None, **kw
    ) -> str:
        """Run an OpenAI-shaped chat completion; return the assistant text."""
        resp = await self._client.chat.completions.create(
            model=model or self.DEFAULT_CHAT_MODEL,
            messages=messages,
            **kw,
        )
        return resp.choices[0].message.content or ""

    async def embed(
        self, texts: list[str], *, model: str | None = None
    ) -> list[list[float]]:
        """Run OpenAI-shaped embeddings; return one vector per input text."""
        resp = await self._client.embeddings.create(
            model=model or self.DEFAULT_EMBED_MODEL,
            input=texts,
        )
        return [d.embedding for d in resp.data]
