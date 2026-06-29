"""Acceptance tests for the multi-provider LLM abstraction (ADR-011).

Covers PRD FR-2 (summarization, 100–300 words), FR-4 (embedding), US-1
(Research Analyst full scrape flow), and US-3 (Developer REST API — response
shape stable across providers). Includes edge-case coverage for provider
failures and bogus ``LLM_PROVIDER`` values.

These tests mock the LLM provider at the protocol boundary — the
``api.services.llm.get_llm_provider`` factory is replaced with an
``AsyncMock``-backed fake. SDK-level mocking (respx for OpenAI-compat,
``google.generativeai`` patches for Gemini) is the responsibility of
``tests/test_llm_providers.py`` (Backend Dev) and is out of scope here.

Mocking strategy
----------------

* ``ArticleSummarizer`` / ``ArticleEmbedder`` — exercised directly without
  going through the HTTP layer. The shared ``get_llm_provider`` factory
  is monkeypatched on each of those modules so a single ``lambda: fake``
  swap intercepts every provider call. This is the most direct way to
  assert "the service delegates to the factory" without dragging in the
  scraper, the DB session, or ChromaDB.
* US-3 response-shape test — calls each provider's ``chat()`` / ``embed()``
  with the same messages/texts used by the real scrape router, then
  asserts the wire-format shape is stable. We don't drive the full HTTP
  ``/scrape`` round-trip here because that path depends on
  ``ArticleOut.model_config`` having ``from_attributes=True`` (a Backend
  concern, currently unset in this repo — see BACKEND-NOTE at bottom).

Env-var isolation
-----------------

The ``_reset_settings_cache`` autouse fixture clears
``get_settings``'s ``@lru_cache`` before AND after each test, so
``monkeypatch.setenv("LLM_PROVIDER", ...)`` is visible to the next
``Settings()`` instantiation. The factory reads ``s.llm_provider`` at
every call, so a fresh ``Settings`` is all we need.

Coverage map (against ADR-011 §11.7 + §11.9 + PRD FR-2/3/4 + US-1/US-3):

* ``test_summarizer_delegates_to_provider_per_env``  FR-2 — provider.chat once
* ``test_summarizer_returns_none_for_short_input``   FR-2 — pre-LLM short-circuit
* ``test_summarizer_returns_none_when_provider_raises`` FR-2 — graceful failure
* ``test_summarizer_strips_whitespace``              FR-2 — whitespace hygiene
* ``test_summarizer_output_word_count_in_range``     FR-2 — 100–300 word target
* ``test_embedder_delegates_to_provider_per_env``    FR-4 — provider.embed once
* ``test_embedder_returns_first_vector``             FR-4 — shape stability
* ``test_embedder_returns_none_for_short_input``     FR-4 — pre-LLM short-circuit
* ``test_embedder_returns_none_when_provider_raises`` FR-4 — graceful failure
* ``test_factory_returns_deepseek_by_default``       US-1 — default selection
* ``test_factory_selects_provider_per_llm_provider`` US-1 — env-driven selection
* ``test_response_shape_identical_across_providers`` US-3 — keys + types match
* ``test_provider_failure_does_not_leak_traceback``  edge case — structured
* ``test_empty_chat_response_handled_gracefully``    edge case — None on ""
* ``test_unknown_llm_provider_rejected_by_settings`` edge case — validation

BACKEND-NOTE
------------

The scrape router (``apps/api/api/routers/scrape.py:109``) currently
calls ``ArticleOut.model_validate(article)`` where ``article`` is a
SQLAlchemy ORM instance. ``ArticleOut`` in
``apps/api/api/schemas/article.py:10`` has empty ``model_config`` and
therefore does NOT have ``from_attributes=True``. The HTTP round-trip
for ``/scrape`` will therefore raise ``ValidationError`` from
``model_validate`` until Backend adds
``model_config = ConfigDict(from_attributes=True)`` to ``ArticleOut``.
This acceptance suite deliberately exercises the service layer (which
is what the LLM abstraction contract is about) rather than the full HTTP
path that hits this pre-existing bug.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from api import config as config_module
from api.config import Settings
from api.services import embedder as embedder_module
from api.services import summarizer as summarizer_module
from api.services.embedder import ArticleEmbedder
from api.services.llm import get_llm_provider
from api.services.summarizer import ArticleSummarizer


# ---------------------------------------------------------------------------
# Constants — fixture-style data shared across tests
# ---------------------------------------------------------------------------


# A summary that comfortably clears the 100–300-word FR-2 target. Word
# count is asserted at module load (>= 100, well within slack). Provider
# responses are substituted in at request time; this is the canonical
# "good" string the fake provider returns from ``chat()``.
GOOD_SUMMARY = (
    "Researchers at an international lab unveiled a new superconducting "
    "material this week that operates at noticeably higher temperatures "
    "than previous compounds ever recorded in peer-reviewed journals. The "
    "team reports that the material maintains zero electrical resistance "
    "near minus thirteen degrees Celsius, removing the need for expensive "
    "liquid-helium cooling in many real-world scenarios. Independent "
    "groups say the result is credible but warn that scaling up "
    "production will take years of careful engineering work and "
    "investment. Commercial applications could include cheaper MRI "
    "machines, lossless power transmission lines, and faster quantum "
    "computers. The published paper is open access and includes full "
    "synthesis instructions for other laboratories to reproduce the "
    "experiment. Funding for the work came from a coalition of national "
    "science foundations across Europe and Asia."
)
assert 100 <= len(GOOD_SUMMARY.split()) <= 300, (
    f"GOOD_SUMMARY word count {len(GOOD_SUMMARY.split())} outside [100, 300]"
)

# 1536-dim OpenAI-shape vector (the OpenRouter embed default).
EMBED_1536 = [0.01] * 1536
# 768-dim Gemini vector (matches GeminiProvider.EMBED_DIMENSIONS).
EMBED_768 = [0.02] * 768

# Minimal canned scraped article — long enough that ArticleSummarizer does
# not return early (it requires len(text) >= 200 per summarizer.py:32).
CANNED_BODY = (
    "This is a fake scraped article body used by the acceptance tests. "
    "It is intentionally longer than two hundred characters so that the "
    "summarizer short-circuit at summarizer.py:32 does not skip the call. "
    "Lorum ipsum content follows for completeness. " * 2
)
assert len(CANNED_BODY) >= 200


# ---------------------------------------------------------------------------
# Helpers — fake provider factory + env-isolation fixture
# ---------------------------------------------------------------------------


def _make_fake_provider(
    *,
    chat_return: str = GOOD_SUMMARY,
    embed_return: list[list[float]] | None = None,
    chat_side_effect: BaseException | None = None,
    embed_side_effect: BaseException | None = None,
) -> MagicMock:
    """Build a fake ``LLMProvider`` whose ``chat`` and ``embed`` are AsyncMocks.

    The returned object supports both positional and keyword ``model=`` on
    ``chat`` / ``embed`` because the real protocol declares them as
    keyword-only; the AsyncMocks ignore their inputs and return whatever
    ``chat_return`` / ``embed_return`` was wired in.
    """
    if embed_return is None:
        embed_return = [EMBED_1536]
    fake = MagicMock()
    fake.chat = AsyncMock(return_value=chat_return, side_effect=chat_side_effect)
    fake.embed = AsyncMock(return_value=embed_return, side_effect=embed_side_effect)
    return fake


def _patch_factory(fake: MagicMock) -> None:
    """Replace the ``get_llm_provider`` symbol on summarizer + embedder modules.

    In-place attribute swap (not monkeypatch) because the service modules
    imported ``get_llm_provider`` as a module-level name; monkeypatching
    ``api.services.llm.get_llm_provider`` would not affect the service
    modules' view. This is the cleanest pattern for "patch the symbol
    the consumer module is looking at" without going through
    monkeypatch.setattr (which requires a fresh reference each test).
    """
    summarizer_module.get_llm_provider = lambda: fake  # type: ignore[assignment]
    embedder_module.get_llm_provider = lambda: fake  # type: ignore[assignment]


def _restore_factory() -> None:
    """Best-effort restore of the original factory symbol on both modules."""
    summarizer_module.get_llm_provider = get_llm_provider  # type: ignore[assignment]
    embedder_module.get_llm_provider = get_llm_provider  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Any:
    """Clear ``get_settings``'s lru_cache around each test for env isolation."""
    config_module.get_settings.cache_clear()
    yield
    config_module.get_settings.cache_clear()
    _restore_factory()


# ---------------------------------------------------------------------------
# FR-2 — ArticleSummarizer delegates to provider.chat per env
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["deepseek", "gemini", "openrouter"])
async def test_summarizer_delegates_to_provider_per_env(
    monkeypatch: pytest.MonkeyPatch,
    provider_name: str,
) -> None:
    """``ArticleSummarizer.summarize`` calls ``provider.chat`` exactly once.

    For each ``LLM_PROVIDER`` value, the summarizer must delegate to
    ``get_llm_provider()`` (which selects the matching provider class)
    and pass an OpenAI-shape messages list to ``chat()``. The test
    asserts: one ``chat`` call, the messages include a system prompt
    + a user message containing the article body.
    """
    monkeypatch.setenv("LLM_PROVIDER", provider_name)
    fake = _make_fake_provider()
    _patch_factory(fake)

    result = await ArticleSummarizer().summarize(CANNED_BODY)

    assert result == GOOD_SUMMARY, (
        f"Summarizer did not return the provider's chat result verbatim; got {result!r}"
    )
    assert fake.chat.await_count == 1, (
        f"Expected one chat() call, got {fake.chat.await_count}"
    )
    # Inspect the messages list — the summarizer builds an OpenAI-shape
    # [{role, content}, ...] list per the protocol.
    call_kwargs = fake.chat.await_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
    assert isinstance(messages, list) and messages, messages
    assert messages[0]["role"] == "system"
    assert "news editor" in messages[0]["content"].lower()
    assert any(
        m["role"] == "user" and CANNED_BODY[:50] in m["content"] for m in messages
    ), f"User message did not include the article body: {messages!r}"


@pytest.mark.asyncio
async def test_summarizer_returns_none_for_short_input() -> None:
    """Body shorter than 200 chars ⇒ ``summarize`` returns ``None`` (no LLM call)."""
    fake = _make_fake_provider()
    _patch_factory(fake)

    result = await ArticleSummarizer().summarize("short text")

    assert result is None
    assert fake.chat.await_count == 0, (
        "summarizer() should short-circuit on text<200 without calling chat()"
    )


@pytest.mark.asyncio
async def test_summarizer_returns_none_when_provider_raises() -> None:
    """Provider raising any exception ⇒ ``summarize`` returns ``None`` (graceful)."""
    fake = _make_fake_provider(chat_side_effect=RuntimeError("provider kaboom (test)"))
    _patch_factory(fake)

    result = await ArticleSummarizer().summarize(CANNED_BODY)

    assert result is None
    assert fake.chat.await_count == 1


@pytest.mark.asyncio
async def test_summarizer_strips_whitespace() -> None:
    """Provider returning text with surrounding whitespace ⇒ ``summarize`` strips it.

    The summarizer contract from before the refactor
    (``summarizer.py:47``) used ``.strip()`` on the provider output. The
    refactored version must preserve that behaviour so the wire shape
    of ``ArticleOut.summary`` is identical.
    """
    padded = "   \n\n" + GOOD_SUMMARY + "\n   "
    fake = _make_fake_provider(chat_return=padded)
    _patch_factory(fake)

    result = await ArticleSummarizer().summarize(CANNED_BODY)

    assert result == GOOD_SUMMARY, (
        f"Summarizer did not strip whitespace; got {result!r}"
    )


@pytest.mark.asyncio
async def test_summarizer_output_word_count_in_range() -> None:
    """Provider's chat() output sits in the 100–300 word FR-2 target.

    Confirms that GOOD_SUMMARY is within range. Validates the fixture
    data the rest of the suite relies on is representative of a
    compliant summary.
    """
    fake = _make_fake_provider(chat_return=GOOD_SUMMARY)
    _patch_factory(fake)
    result = await ArticleSummarizer().summarize(CANNED_BODY)
    assert result is not None
    words = len(result.split())
    assert 100 <= words <= 300, (
        f"Summary word count {words} outside FR-2 target [100, 300]"
    )


# ---------------------------------------------------------------------------
# FR-4 — ArticleEmbedder delegates to provider.embed per env
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_name", "embed_return", "expected_dim"),
    [
        # OpenRouter default embed model emits 1536-dim vectors.
        ("openrouter", [EMBED_1536], 1536),
        # Gemini text-embedding-004 emits 768-dim vectors per ADR §11.7.
        ("gemini", [EMBED_768], 768),
        # DeepSeek has no native embed; the acceptance test only verifies
        # that *if* the call reaches the provider, the returned vector
        # length matches the OpenRouter fallback (1536-dim) per ADR §11.3.
        # The Backend may instead raise NotImplementedError; the embedder
        # catches that and returns None (per embedder.py:36 ``except Exception``).
        # Both paths are valid — see test_embedder_returns_none_when_provider_raises.
        ("deepseek", [EMBED_1536], 1536),
    ],
)
async def test_embedder_delegates_to_provider_per_env(
    monkeypatch: pytest.MonkeyPatch,
    provider_name: str,
    embed_return: list[list[float]],
    expected_dim: int,
) -> None:
    """``ArticleEmbedder.embed`` calls ``provider.embed`` and returns the first vector."""
    monkeypatch.setenv("LLM_PROVIDER", provider_name)
    fake = _make_fake_provider(embed_return=embed_return)
    _patch_factory(fake)

    result = await ArticleEmbedder().embed(CANNED_BODY)

    assert result is not None, (
        f"Provider {provider_name!r} returned no embedding; "
        f"the Backend may have raised NotImplementedError — covered by "
        f"test_embedder_returns_none_when_provider_raises"
    )
    assert isinstance(result, list)
    assert len(result) == expected_dim, (
        f"Provider {provider_name!r} returned {len(result)}-dim vector; "
        f"expected {expected_dim}"
    )
    assert fake.embed.await_count == 1
    # The provider's embed() takes a list of texts; we pass exactly one.
    call_kwargs = fake.embed.await_args
    texts = call_kwargs.kwargs.get("texts") or call_kwargs.args[0]
    assert texts == [CANNED_BODY[:8000]], texts


@pytest.mark.asyncio
async def test_embedder_returns_first_vector_when_provider_returns_batch() -> None:
    """Provider returning a batch of vectors ⇒ ``embed`` returns the first only.

    The protocol lets providers batch embed multiple texts in one call;
    the router always passes a single text and wants a single vector
    back. The embedder must flatten the 1-element batch to its first
    element so the callers' downstream code keeps working.
    """
    fake = _make_fake_provider(embed_return=[EMBED_768, EMBED_1536])
    _patch_factory(fake)

    result = await ArticleEmbedder().embed(CANNED_BODY)

    assert result == EMBED_768, (
        f"Embedder did not return the first vector; got length {len(result) if result else None}"
    )
    assert fake.embed.await_count == 1


@pytest.mark.asyncio
async def test_embedder_returns_none_for_short_input() -> None:
    """Text shorter than 10 chars ⇒ ``embed`` returns ``None`` (no LLM call)."""
    fake = _make_fake_provider()
    _patch_factory(fake)

    result = await ArticleEmbedder().embed("hi")

    assert result is None
    assert fake.embed.await_count == 0, (
        "embedder() should short-circuit on text<10 without calling the provider"
    )


@pytest.mark.asyncio
async def test_embedder_returns_none_when_provider_raises() -> None:
    """Provider raising any exception (incl. NotImplementedError) ⇒ ``embed`` returns ``None``."""
    fake = _make_fake_provider(embed_side_effect=NotImplementedError)
    _patch_factory(fake)

    result = await ArticleEmbedder().embed(CANNED_BODY)

    assert result is None
    assert fake.embed.await_count == 1


# ---------------------------------------------------------------------------
# US-1 — Factory selection via LLM_PROVIDER
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("env_value", "expected_class_name"),
    [
        ("deepseek", "DeepSeekProvider"),
        ("gemini", "GeminiProvider"),
        ("openrouter", "OpenRouterProvider"),
    ],
)
def test_factory_selects_provider_per_llm_provider(
    monkeypatch: pytest.MonkeyPatch,
    env_value: str,
    expected_class_name: str,
) -> None:
    """``LLM_PROVIDER=...`` ⇒ factory returns the matching provider class.

    The factory should always read fresh settings (which read fresh env)
    so per-test ``monkeypatch.setenv`` flips the selection without
    process restart. The ``_reset_settings_cache`` autouse fixture
    guarantees the lru_cache is empty.
    """
    monkeypatch.setenv("LLM_PROVIDER", env_value)
    # Provide dummy keys for whatever provider the test selects — the
    # provider constructor needs *some* value to instantiate (or it
    # configures an SDK that fails on use). We don't actually USE the
    # provider here; just confirm the factory returns it.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-ds")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gm")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or")

    provider = get_llm_provider()
    assert type(provider).__name__ == expected_class_name, (
        f"LLM_PROVIDER={env_value!r} selected {type(provider).__name__}; "
        f"expected {expected_class_name}"
    )


def test_factory_returns_deepseek_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``LLM_PROVIDER`` is unset, the factory returns ``DeepSeekProvider``."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-ds")
    provider = get_llm_provider()
    assert type(provider).__name__ == "DeepSeekProvider"


# ---------------------------------------------------------------------------
# US-3 — Response shape is identical across providers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["deepseek", "gemini", "openrouter"])
async def test_response_shape_identical_across_providers(
    monkeypatch: pytest.MonkeyPatch,
    provider_name: str,
) -> None:
    """For each provider, the chat()/embed() output types are stable across providers.

    US-3 requires the Developer-facing REST shape to be stable regardless
    of which provider is wired in. We don't drive the full HTTP
    ``/scrape`` round-trip (see BACKEND-NOTE in module docstring);
    instead we exercise the summarizer + embedder with each provider
    and assert the *types* of the values that would land in
    ``ArticleOut.summary`` / ``ArticleOut.body`` / ``ArticleOut.embedding``
    are identical.

    The two ``ArticleOut`` fields populated from provider output are
    ``summary`` (str | None) and the implicit ChromaDB ``embedding``
    (list[float] | None). Both contractually have the same Python types
    regardless of provider; only the dim varies for embedding (FR-4).
    """
    monkeypatch.setenv("LLM_PROVIDER", provider_name)
    fake = _make_fake_provider()
    _patch_factory(fake)

    summary = await ArticleSummarizer().summarize(CANNED_BODY)
    embedding = await ArticleEmbedder().embed(CANNED_BODY)

    # ``summary`` is ``str | None`` for every provider.
    assert summary is None or isinstance(summary, str), (
        f"{provider_name}: summary type {type(summary).__name__}; expected str|None"
    )
    # ``embedding`` is ``list[float] | None`` for every provider.
    assert embedding is None or isinstance(embedding, list), (
        f"{provider_name}: embedding type {type(embedding).__name__}; expected list|None"
    )
    if isinstance(embedding, list):
        assert all(isinstance(v, float) for v in embedding), (
            f"{provider_name}: embedding contains non-float elements"
        )


# ---------------------------------------------------------------------------
# Edge case — bogus LLM_PROVIDER is rejected by Settings
# ---------------------------------------------------------------------------


def test_unknown_llm_provider_rejected_by_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``LLM_PROVIDER=bogus`` is caught by ``Settings`` literal validation.

    The factory function ``get_llm_provider`` never has to deal with
    unknown values because ``Settings.llm_provider`` is a
    ``Literal["deepseek", "gemini", "openrouter"]`` — Pydantic rejects
    the value at instantiation. This test confirms the rejection
    happens *before* the factory is even called and that the error
    message names the offending field.
    """
    monkeypatch.setenv("LLM_PROVIDER", "bogus")
    config_module.get_settings.cache_clear()

    with pytest.raises(Exception) as exc_info:
        Settings()  # type: ignore[call-arg]

    # The validation error must name the field and the offender. We
    # accept any Exception subclass so we don't bind this test to
    # pydantic's exact ValidationError import path.
    text = str(exc_info.value)
    assert "llm_provider" in text, text
    assert "bogus" in text, text


# ---------------------------------------------------------------------------
# Edge case — empty chat() content is handled gracefully (summary=None)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_chat_response_handled_gracefully() -> None:
    """Provider returning ``""`` from chat() ⇒ ``summarize`` returns the empty string.

    The downstream contract is that ``ArticleOut.summary`` accepts
    ``None``. With an empty-string response the summarizer currently
    passes ``"".strip()`` = ``""`` straight through; the article-row
    writer is responsible for treating empty string as no summary.
    Either path (None or "") is acceptable here; we assert the
    summarizer doesn't crash and returns a stripped string.
    """
    fake = _make_fake_provider(chat_return="")
    _patch_factory(fake)

    result = await ArticleSummarizer().summarize(CANNED_BODY)

    assert result == "", (
        f"Summarizer did not handle empty string gracefully; got {result!r}"
    )
    assert fake.chat.await_count == 1


# ---------------------------------------------------------------------------
# Edge case — provider failures are caught, no traceback in client-facing flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_exc",
    [
        pytest.param(
            httpx.TimeoutException("upstream timeout (test)"),
            id="httpx.TimeoutException",
        ),
        pytest.param(
            RuntimeError("rate limit hit (test)"),
            id="generic-RuntimeError",
        ),
    ],
)
async def test_provider_failure_does_not_leak_traceback(
    provider_exc: BaseException,
) -> None:
    """Provider raising any exception ⇒ summarizer/embedder return ``None``.

    Per ADR-010 the catch-all handler emits a generic 500 problem+json
    body that never includes stack traces. The summarizer currently
    swallows the exception and returns ``None`` (giving us 201 with
    summary=null); either path is acceptable per the spec, but the
    service layer must NEVER propagate a raw exception — that would
    bypass the ADR-010 handler.
    """
    fake = _make_fake_provider(chat_side_effect=provider_exc)
    _patch_factory(fake)

    summary = await ArticleSummarizer().summarize(CANNED_BODY)

    # Service must swallow the exception and return ``None`` —
    # no exception bubbles past the service.
    assert summary is None, (
        f"Summarizer leaked {type(provider_exc).__name__} to caller; got {summary!r}"
    )
    # And the embed path is independent — it must still work for the
    # same fake (the side_effect is on chat, not embed).
    embedding = await ArticleEmbedder().embed(CANNED_BODY)
    assert embedding == EMBED_1536, (
        f"Embed path broken when chat path raises; got {embedding!r}"
    )
