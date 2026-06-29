"""Tests for the multi-provider LLM abstraction (ADR-011 §11.9).

Covers:
    * Factory selection: ``get_llm_provider`` resolves ``LLM_PROVIDER``
      env var to the right class and raises ``ValueError`` on unknown.
    * OpenAI-compatible providers (DeepSeek, OpenRouter): ``respx``
      intercepts HTTP and we assert request body + return value.
    * Gemini provider: ``unittest.mock`` against the
      ``google.generativeai`` SDK (``GenerativeModel`` for chat,
      ``embed_content_async`` for embed); assert 768-dim output.
    * Refactored ``ArticleSummarizer`` / ``ArticleEmbedder``: monkeypatch
      ``get_llm_provider`` and assert they delegate correctly.

No provider requires a live API key in CI.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from api.config import get_settings
from api.services import embedder as embedder_module
from api.services import summarizer as summarizer_module
from api.services.llm import get_llm_provider
from api.services.llm.deepseek import DeepSeekProvider
from api.services.llm.gemini import GeminiProvider
from api.services.llm.openrouter import OpenRouterProvider


# ---------------------------------------------------------------------------
# §11.9.1 — Factory selection
# ---------------------------------------------------------------------------


def _set_provider(monkeypatch: pytest.MonkeyPatch, name: str, **overrides: str) -> None:
    """Override the cached ``Settings`` so the factory reads the new value.

    ``get_settings`` is ``@lru_cache``-d, so we patch the singleton
    rather than the env vars — env-var mutation would not be picked
    up across the cached call.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", name)
    for key, value in overrides.items():
        monkeypatch.setattr(settings, key, value)


def test_get_llm_provider_returns_deepseek_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No override → ``DeepSeekProvider`` (the cost-default per ADR-011 §11.6)."""
    _set_provider(monkeypatch, "deepseek", deepseek_api_key="sk-ds-test")
    provider = get_llm_provider()
    assert isinstance(provider, DeepSeekProvider)
    assert provider.DEFAULT_CHAT_MODEL == "deepseek-chat"


def test_get_llm_provider_returns_gemini_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``LLM_PROVIDER=gemini`` → ``GeminiProvider`` with EMBED_DIMENSIONS=768."""
    _set_provider(monkeypatch, "gemini", gemini_api_key="gm-test")
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)
    assert GeminiProvider.EMBED_DIMENSIONS == 768
    assert GeminiProvider.DEFAULT_EMBED_MODEL == "text-embedding-004"


def test_get_llm_provider_uses_google_api_key_as_gemini_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``google_api_key`` mirrors ``gemini_api_key`` per CLAUDE.md TaskMaster config."""
    _set_provider(monkeypatch, "gemini", gemini_api_key="", google_api_key="g-fb")
    with patch("api.services.llm.gemini.genai.configure") as configure_mock:
        GeminiProvider(api_key="g-fb")
        configure_mock.assert_called_once_with(api_key="g-fb")


def test_get_llm_provider_returns_openrouter_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``LLM_PROVIDER=openrouter`` → ``OpenRouterProvider``."""
    _set_provider(monkeypatch, "openrouter", openrouter_api_key="or-test")
    provider = get_llm_provider()
    assert isinstance(provider, OpenRouterProvider)
    assert provider.DEFAULT_EMBED_MODEL == "openai/text-embedding-3-small"


def test_get_llm_provider_raises_on_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown provider name → ``ValueError`` carrying the bad value."""
    _set_provider(monkeypatch, "bogus")
    with pytest.raises(ValueError, match="bogus"):
        get_llm_provider()


# ---------------------------------------------------------------------------
# §11.9.2 — OpenAI-compat providers (respx)
# ---------------------------------------------------------------------------


def _openai_chat_payload(content: str, model: str = "deepseek-chat") -> dict[str, Any]:
    return {
        "id": "cmpl-test",
        "object": "chat.completion",
        "created": 1_700_000_000,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
    }


def _openai_embed_payload(
    vectors: Iterable[Iterable[float]], model: str = "text-embedding-3-small"
) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "embedding": list(v), "index": i}
            for i, v in enumerate(vectors)
        ],
        "model": model,
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }


@pytest.mark.asyncio
async def test_deepseek_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """DeepSeek chat posts to ``/chat/completions`` with OpenAI-shape body."""
    monkeypatch.setattr(get_settings(), "deepseek_api_key", "sk-ds")
    with respx.mock(base_url="https://api.deepseek.com") as mock:
        route = mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200, json=_openai_chat_payload("deepseek summary")
            )
        )
        provider = DeepSeekProvider(api_key="sk-ds")
        out = await provider.chat(
            [{"role": "user", "content": "Summarize this"}],
            temperature=0.2,
        )
    assert out == "deepseek summary"
    assert route.called
    # Request body must match OpenAI shape: model + messages + the kwargs we passed.
    sent = route.calls.last.request
    import json as _json

    body = _json.loads(sent.content)
    assert body["model"] == "deepseek-chat"
    assert body["messages"] == [{"role": "user", "content": "Summarize this"}]
    assert body["temperature"] == 0.2


@pytest.mark.asyncio
async def test_deepseek_embed_raises_not_implemented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DeepSeek has no native embed → ``NotImplementedError`` per ADR-011 §11.3."""
    monkeypatch.setattr(get_settings(), "deepseek_api_key", "sk-ds")
    provider = DeepSeekProvider(api_key="sk-ds")
    with pytest.raises(NotImplementedError):
        await provider.embed(["anything"])


@pytest.mark.asyncio
async def test_openrouter_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenRouter chat posts to ``/api/v1/chat/completions`` with OpenAI shape."""
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "sk-or")
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        route = mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json=_openai_chat_payload(
                    "openrouter says hi",
                    model="openai/gpt-4o-mini",
                ),
            )
        )
        provider = OpenRouterProvider(api_key="sk-or")
        out = await provider.chat([{"role": "user", "content": "yo"}])
    assert out == "openrouter says hi"
    assert route.called
    import json as _json

    body = _json.loads(route.calls.last.request.content)
    assert body["model"] == "openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_openrouter_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenRouter embed returns one vector per input in input order."""
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "sk-or")
    vectors = ([0.1, 0.2, 0.3], [0.4, 0.5, 0.6])
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        route = mock.post("/embeddings").mock(
            return_value=httpx.Response(
                200,
                json=_openai_embed_payload(
                    vectors, model="openai/text-embedding-3-small"
                ),
            )
        )
        provider = OpenRouterProvider(api_key="sk-or")
        out = await provider.embed(["a", "b"])
    assert out == [list(v) for v in vectors]
    assert route.called
    import json as _json

    body = _json.loads(route.calls.last.request.content)
    assert body["model"] == "openai/text-embedding-3-small"
    assert body["input"] == ["a", "b"]


# ---------------------------------------------------------------------------
# §11.9.3 — Gemini provider (unittest.mock against the SDK)
# ---------------------------------------------------------------------------


def _mock_gemini_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


def _mock_gemini_embedding(values: list[float]) -> MagicMock:
    emb = MagicMock()
    emb.values = values
    resp = MagicMock()
    resp.embedding = emb
    return resp


@pytest.mark.asyncio
async def test_gemini_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """``chat()`` translates OpenAI-shape messages and returns the SDK text."""
    _set_provider(monkeypatch, "gemini", gemini_api_key="gm")
    with patch("api.services.llm.gemini.genai.GenerativeModel") as gm_ctor:
        model_mock = MagicMock()
        model_mock.generate_content = MagicMock(
            return_value=_mock_gemini_response("gemini says hi")
        )
        gm_ctor.return_value = model_mock
        provider = GeminiProvider(api_key="gm")
        out = await provider.chat(
            [
                {"role": "system", "content": "you are concise"},
                {"role": "user", "content": "summarize"},
            ],
        )
    assert out == "gemini says hi"
    # System instruction was hoisted out of the messages list.
    gm_ctor.assert_called_once()
    _, kwargs = gm_ctor.call_args
    assert kwargs["system_instruction"] == "you are concise"
    assert kwargs["model_name"] == "gemini-1.5-flash"


@pytest.mark.asyncio
async def test_gemini_embed_returns_768_dim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``embed()`` returns 768-dim vectors as documented for text-embedding-004."""
    _set_provider(monkeypatch, "gemini", gemini_api_key="gm")
    with patch(
        "api.services.llm.gemini.genai.embed_content_async",
        new=AsyncMock(
            side_effect=[
                _mock_gemini_embedding([0.0] * 768),
                _mock_gemini_embedding([0.1] * 768),
            ]
        ),
    ) as embed_mock:
        provider = GeminiProvider(api_key="gm")
        out = await provider.embed(["hello", "world"])
    assert len(out) == 2
    assert all(len(v) == GeminiProvider.EMBED_DIMENSIONS == 768 for v in out)
    # The model name must be the Gemini default unless overridden.
    assert embed_mock.await_count == 2
    first_kwargs = embed_mock.await_args_list[0].kwargs
    assert first_kwargs["model"] == "text-embedding-004"


# ---------------------------------------------------------------------------
# §11.9.4 — Refactored services delegate to the factory
# ---------------------------------------------------------------------------


class _FakeProvider:
    """Records chat/embed calls; used to assert delegating behaviour."""

    def __init__(
        self, chat_text: str = "fake summary", embed_vec: list[float] | None = None
    ):
        self.chat_text = chat_text
        self.embed_vec = embed_vec if embed_vec is not None else [0.0, 0.1, 0.2]
        self.chat_calls: list[tuple[list[dict], dict]] = []
        self.embed_calls: list[tuple[list[str], dict]] = []

    async def chat(self, messages, *, model=None, **kw):
        self.chat_calls.append((list(messages), dict(kw)))
        return self.chat_text

    async def embed(self, texts, *, model=None):
        self.embed_calls.append((list(texts), {}))
        return [self.embed_vec] * len(texts)


@pytest.mark.asyncio
async def test_summarizer_delegates_to_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ArticleSummarizer.summarize`` calls ``provider.chat`` with the right shape."""
    fake = _FakeProvider(chat_text="  short summary  ")
    monkeypatch.setattr(summarizer_module, "get_llm_provider", lambda: fake)

    summarizer = summarizer_module.ArticleSummarizer()
    out = await summarizer.summarize("This article is long enough. " * 100)

    assert out == "short summary"  # stripped
    assert len(fake.chat_calls) == 1
    messages, kw = fake.chat_calls[0]
    # System prompt is the first message; user payload is the second.
    assert messages[0]["role"] == "system"
    assert "news editor" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"].startswith("Summarize:")
    # Generation kwargs surface in the call.
    assert kw.get("max_tokens") == 600
    assert kw.get("temperature") == 0.2


@pytest.mark.asyncio
async def test_summarizer_returns_none_on_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider raising → summarizer returns ``None`` and logs a warning."""

    class _Boom:
        async def chat(self, messages, *, model=None, **kw):
            raise RuntimeError("upstream down")

    monkeypatch.setattr(summarizer_module, "get_llm_provider", lambda: _Boom())
    summarizer = summarizer_module.ArticleSummarizer()
    out = await summarizer.summarize("This article is long enough. " * 100)
    assert out is None


@pytest.mark.asyncio
async def test_summarizer_skips_short_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Input below the 200-char floor → ``None`` without touching the provider."""
    fake = _FakeProvider()
    monkeypatch.setattr(summarizer_module, "get_llm_provider", lambda: fake)
    summarizer = summarizer_module.ArticleSummarizer()
    out = await summarizer.summarize("too short")
    assert out is None
    assert fake.chat_calls == []


@pytest.mark.asyncio
async def test_embedder_delegates_to_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ArticleEmbedder.embed`` returns the first vector from ``provider.embed``."""
    fake = _FakeProvider(embed_vec=[0.5, 0.6, 0.7])
    monkeypatch.setattr(embedder_module, "get_llm_provider", lambda: fake)
    embedder = embedder_module.ArticleEmbedder()
    out = await embedder.embed("hello world, this is text over the 10-char floor")
    assert out == [0.5, 0.6, 0.7]
    assert len(fake.embed_calls) == 1
    texts, _ = fake.embed_calls[0]
    assert texts == ["hello world, this is text over the 10-char floor"]


@pytest.mark.asyncio
async def test_embedder_returns_none_on_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider raising → embedder returns ``None``."""

    class _Boom:
        async def embed(self, texts, *, model=None):
            raise RuntimeError("upstream down")

    monkeypatch.setattr(embedder_module, "get_llm_provider", lambda: _Boom())
    embedder = embedder_module.ArticleEmbedder()
    out = await embedder.embed("hello world, this is text over the 10-char floor")
    assert out is None


@pytest.mark.asyncio
async def test_embedder_skips_short_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Input below the 10-char floor → ``None`` without touching the provider."""
    fake = _FakeProvider()
    monkeypatch.setattr(embedder_module, "get_llm_provider", lambda: fake)
    embedder = embedder_module.ArticleEmbedder()
    out = await embedder.embed("hi")
    assert out is None
    assert fake.embed_calls == []
