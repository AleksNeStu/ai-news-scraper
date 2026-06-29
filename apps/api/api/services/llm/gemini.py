"""Gemini provider — native Google SDK.

Per ADR-011 §11.3. Uses ``google.generativeai`` rather than an
OpenAI-shape wrapper because Gemini's request/response shape is
genuinely different. Outward protocol matches ``LLMProvider`` so
callers see one shape across all three providers.

Note: ``google.generativeai`` is on a deprecation path in favor of the
new ``google.genai`` SDK. We pin to ``google-generativeai ^0.8`` per
ADR-011; a future migration is tracked separately.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import google.generativeai as genai

from .base import LLMProvider


class GeminiProvider(LLMProvider):
    """Native Google SDK — different request shape, same outward protocol."""

    DEFAULT_CHAT_MODEL = "gemini-1.5-flash"
    DEFAULT_EMBED_MODEL = "text-embedding-004"
    EMBED_DIMENSIONS = 768

    def __init__(self, api_key: str) -> None:
        genai.configure(api_key=api_key)

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        **kw,
    ) -> str:
        """Translate OpenAI-shape messages into Gemini contents and call the SDK."""
        system_instruction, contents = _split_system(messages)
        gen_model = genai.GenerativeModel(
            model_name=model or self.DEFAULT_CHAT_MODEL,
            system_instruction=system_instruction,
            **kw,
        )
        # ``generate_content`` is sync; run it on a worker thread so the
        # event loop stays responsive.
        resp = await asyncio.to_thread(gen_model.generate_content, contents)
        return _extract_text(resp)

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Run ``embed_content`` for each input; return vectors in input order."""
        embed_model = model or self.DEFAULT_EMBED_MODEL
        # ``embed_content_async`` is the native async entry point.
        out: list[list[float]] = []
        for text in texts:
            resp = await genai.embed_content_async(
                model=embed_model,
                content=text,
            )
            out.append(_extract_embedding(resp))
        return out


def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Pull the first system message out of an OpenAI-shape messages list.

    Gemini takes the system instruction as a separate constructor arg,
    not as part of ``contents``. Returns ``(system, contents)``; either
    may be ``None`` / empty.
    """
    system: str | None = None
    contents: list[dict] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system" and system is None:
            system = content if isinstance(content, str) else str(content)
            continue
        if role in {"user", "model"}:
            contents.append({"role": role, "parts": [_to_part(content)]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [_to_part(content)]})
        elif role == "system":
            # Multiple system messages are concatenated into the system prompt.
            extra = content if isinstance(content, str) else str(content)
            system = (system + "\n\n" + extra) if system else extra
    return system, contents


def _to_part(content: object) -> dict:
    """Wrap a free-form message content into a Gemini ``text`` part."""
    if isinstance(content, str):
        return {"text": content}
    return {"text": str(content)}


def _extract_text(resp: object) -> str:
    """Pluck the assistant text out of a Gemini ``GenerateContentResponse``."""
    text = getattr(resp, "text", None)
    if text:
        return text
    # Fallback: walk candidates/parts if ``.text`` is empty (e.g. safety block).
    candidates: Iterable | None = getattr(resp, "candidates", None)
    if not candidates:
        return ""
    for cand in candidates:
        content = getattr(cand, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", []):
            t = getattr(part, "text", None)
            if t:
                return t
    return ""


def _extract_embedding(resp: object) -> list[float]:
    """Pluck a single embedding vector out of an ``embed_content`` response."""
    emb = getattr(resp, "embedding", None)
    if emb is None:
        raise RuntimeError(f"Gemini embed_content returned no embedding: {resp!r}")
    values = getattr(emb, "values", None)
    if values is None:
        raise RuntimeError(f"Gemini embedding missing values: {emb!r}")
    return list(values)
