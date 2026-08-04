"""Embedding playground service layer.

Task #34 / ADR-022. Wraps the LLM factory at
``apps/api/api/services/llm/__init__.py`` with three operations:

* ``list_providers()`` — enumerate every registered provider, computing
  ``supports_embed``, ``key_configured``, dimensions, and default model
  statically (no instantiation) so a missing SDK or absent key cannot
  break the picker endpoint.
* ``embed_text(provider_id, text, model=None)`` — resolve a single
  provider, call ``provider.embed([text][:8000])``, return the first
  vector. Translates ``NotImplementedError`` and missing-key errors
  into our typed ``AppException`` subclasses so the router can map
  them to HTTP 422 (ADR-022 §22.4, §22.5).
* ``cosine_similarity`` / ``dot_product`` / ``euclidean`` — pure
  ``math`` ops. Caller-side precondition: vector lengths equal.

Design constraints (re-checked against ADR-022):

* The router never returns the key value (ADR §22.5); this service
  reads ``Settings.<provider>_api_key`` and exposes only the boolean
  ``key_configured``.
* Per ADR §22.7 the API returns the FULL vector; no truncation here.
* Per ADR §22.8 no caching is layered in — every call hits the model.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from api.config import Settings, get_settings
from api.schemas.embeddings import EmbeddingProvider
from api.services.llm.base import LLMProvider
from api.services.llm.deepseek import DeepSeekProvider
from api.services.llm.gemini import GeminiProvider
from api.services.llm.openrouter import OpenRouterProvider

# --- AppException subclasses (mapped to HTTP 422 in the router) ---------


class ProviderDoesNotSupportEmbedding(Exception):
    """Raised when the chosen provider's ``embed()`` is not implemented.

    Maps to ``HTTP 422`` with ``error_code="provider_does_not_support_embedding"``
    per ADR-022 §22.4 (DeepSeek is the in-tree example).
    """


class ProviderKeyMissing(Exception):
    """Raised when the chosen provider requires its own API key but it
    is not configured in the deployment env.

    Maps to ``HTTP 422`` with ``error_code="provider_key_missing"``
    per ADR-022 §22.5.
    """


class ProviderUnknown(Exception):
    """Raised when ``provider_id`` does not match a registered provider.

    Maps to ``HTTP 422`` with ``error_code="provider_unknown"``
    per ADR-022 §22.5.
    """


# --- Provider registry (single source of truth, mirrors the factory) ----


@dataclass(frozen=True)
class _ProviderSpec:
    """Static metadata + factory for one registered provider.

    ``supports_embed`` is computed per-call from ``cls.embed`` identity
    (the DeepSeek override is the only "NotImplementedError" stub in
    v1) so the registry does not need per-class branching.

    ``key_resolver`` returns the matching settings field, falling back
    to the empty string when the key is absent; callers treat empty as
    "not configured" and never read the value off the wire.
    """

    id: str
    display_name: str
    cls: type
    key_resolver: Callable[[Settings], str]
    # ``True`` in v1 for every provider (ADR-022 §22.5). The flag is
    # kept on the spec so a future relaxation (per-call override) can
    # drop it selectively without touching the router.
    requires_own_key: bool = True


# Order matters only for response stability; downstream callers sort by
# a stable key if they care.
_PROVIDER_SPECS: tuple[_ProviderSpec, ...] = (
    _ProviderSpec(
        id="deepseek",
        display_name="DeepSeek",
        cls=DeepSeekProvider,
        # No mirror — deepseek_api_key is the only field.
        key_resolver=lambda s: s.deepseek_api_key,
    ),
    _ProviderSpec(
        id="gemini",
        display_name="Google Gemini",
        cls=GeminiProvider,
        # Gemini key may live in either gemini_api_key or google_api_key
        # (mirrors the factory's selection logic at
        # ``services/llm/__init__.py:24``).
        key_resolver=lambda s: s.gemini_api_key or s.google_api_key,
    ),
    _ProviderSpec(
        id="openrouter",
        display_name="OpenRouter",
        cls=OpenRouterProvider,
        key_resolver=lambda s: s.openrouter_api_key,
    ),
)


# The deepest test for "supports embed" — comparing the bound method
# to DeepSeek's stub.  Any provider whose ``embed`` is anything other
# than DeepSeek's NotImplementedError override counts as supporting
# embeddings (Gemini has a real override, OpenAI compat has the base
# override, both differ from DeepSeekProvider.embed by identity).
_DEEPSEEK_EMBED = DeepSeekProvider.embed


def _resolve_spec(provider_id: str) -> _ProviderSpec:
    """Look up a provider spec by id or raise ``ProviderUnknown``."""
    for spec in _PROVIDER_SPECS:
        if spec.id == provider_id:
            return spec
    raise ProviderUnknown(f"Provider {provider_id!r} is not registered.")


def _instantiate(spec: _ProviderSpec, settings: Settings) -> LLMProvider:
    """Build a provider instance from the matching settings key.

    Mirrors ``get_llm_provider``'s argument shape for each subclass so
    constructing an embedding-only request does not require the
    caller to know the per-class quirks (e.g. Gemini's
    ``api_key or google_api_key`` fallback).
    """
    api_key = spec.key_resolver(settings)
    return spec.cls(api_key=api_key)


# --- Public surface ------------------------------------------------------


def list_providers(settings: Settings | None = None) -> list[EmbeddingProvider]:
    """Return one ``EmbeddingProvider`` entry per registered provider.

    Static walk over ``_PROVIDER_SPECS`` — no instantiation, no SDK
    imports, no network. The bool ``key_configured`` reflects current
    settings; the key value itself is never copied into the response.

    Args:
        settings: Optional override for testability. ``None`` reads
            ``get_settings()`` (the production path).
    """
    s = settings if settings is not None else get_settings()
    out: list[EmbeddingProvider] = []
    for spec in _PROVIDER_SPECS:
        raw_key = spec.key_resolver(s)
        key_configured = bool(raw_key) and raw_key != "sk-replace-me"
        supports_embed = spec.cls.embed is not _DEEPSEEK_EMBED
        out.append(
            EmbeddingProvider(
                id=spec.id,
                display_name=spec.display_name,
                supports_embed=supports_embed,
                requires_own_key=spec.requires_own_key,
                key_configured=key_configured,
                dimensions=getattr(spec.cls, "EMBED_DIMENSIONS", None)
                if supports_embed
                else None,
                default_model=getattr(spec.cls, "DEFAULT_EMBED_MODEL", None)
                if supports_embed
                else None,
            )
        )
    return out


async def embed_text(
    provider_id: str,
    text: str,
    *,
    model: str | None = None,
    settings: Settings | None = None,
) -> tuple[str, int, list[float]]:
    """Embed a single text against one provider; return ``(model, dims, vec)``.

    Args:
        provider_id: One of the ids surfaced by ``list_providers``.
        text: Input text. Server-side truncation to 8000 chars matches
            ``apps/api/api/services/embedder.py:31`` (Pydantic also
            enforces this at the boundary).
        model: Optional override; falls back to the provider's
            ``DEFAULT_EMBED_MODEL`` when ``None``.
        settings: Optional override for testability.

    Returns:
        Tuple ``(model, dimensions, vector)``. ``model`` is the
        resolved value (request value or provider default), so callers
        can echo it in the response.

    Raises:
        ProviderUnknown: ``provider_id`` not in the registry (422).
        ProviderKeyMissing: provider requires a key but it's not set
            (422).
        ProviderDoesNotSupportEmbedding: provider's ``embed()`` raises
            ``NotImplementedError`` (422 — defence in depth per
            ADR-022 §22.4).
    """
    s = settings if settings is not None else get_settings()
    spec = _resolve_spec(provider_id)
    if spec.requires_own_key:
        raw_key = spec.key_resolver(s)
        if not raw_key or raw_key == "sk-replace-me":
            raise ProviderKeyMissing(
                f"Provider {provider_id!r} requires an API key that "
                "is not configured on the server."
            )

    truncated = text[:8000]
    resolved_model = model or getattr(spec.cls, "DEFAULT_EMBED_MODEL", "") or ""

    try:
        provider = _instantiate(spec, s)
        vectors = await _await_embed(provider, [truncated], resolved_model)
    except NotImplementedError as exc:
        # Defence in depth — DeepSeek raises here even though the
        # picker promises ``supports_embed: false``.
        raise ProviderDoesNotSupportEmbedding(
            f"Provider {provider_id!r} does not support embedding."
        ) from exc

    if not vectors:
        raise ProviderDoesNotSupportEmbedding(
            f"Provider {provider_id!r} returned no embedding vector."
        )
    vector = list(vectors[0])
    dimensions = len(vector)
    return resolved_model, dimensions, vector


async def _await_embed(
    provider: Any, texts: list[str], model: str
) -> list[list[float]]:
    """Await ``provider.embed`` whether or not it returned a coroutine.

    Keeps the test suite ``monkeypatch``-friendly: a fake provider that
    returns a list (not a coroutine) stays a valid stand-in.
    """
    result = provider.embed(texts, model=model)
    if hasattr(result, "__await__"):
        return await result  # type: ignore[return-value]
    return result  # type: ignore[return-value]


# --- Math primitives -----------------------------------------------------


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in ``[-1, 1]`` for two non-empty, equal-length vectors.

    Asserts the precondition explicitly so a contract violation
    surfaces immediately rather than silently producing a wrong number
    (per ADR-022 §22.3 the schema enforces ``ge=-1, le=1`` and the
    vector lengths come from the same provider's call).
    """
    if len(a) != len(b):
        raise ValueError(
            f"cosine_similarity: length mismatch {len(a)} != {len(b)}"
        )
    if not a:
        raise ValueError("cosine_similarity: empty vector")
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = math.sqrt(sum(float(x) * float(x) for x in a))
    nb = math.sqrt(sum(float(y) * float(y) for y in b))
    if na == 0.0 or nb == 0.0:
        # One of the vectors is the zero vector — cosine is undefined;
        # return 0.0 (convention used in the spec smoke-test expectations).
        return 0.0
    value = dot / (na * nb)
    # Numerical drift can push us slightly outside [-1, 1]; clamp so the
    # Pydantic schema (``ge=-1.0, le=1.0``) accepts the value.
    if value > 1.0:
        return 1.0
    if value < -1.0:
        return -1.0
    return value


def dot_product(a: Sequence[float], b: Sequence[float]) -> float:
    """Raw dot product; raises on length mismatch or empty input."""
    if len(a) != len(b):
        raise ValueError(
            f"dot_product: length mismatch {len(a)} != {len(b)}"
        )
    if not a:
        raise ValueError("dot_product: empty vector")
    return sum(float(x) * float(y) for x, y in zip(a, b))


def euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    """Euclidean distance; raises on length mismatch or empty input."""
    if len(a) != len(b):
        raise ValueError(
            f"euclidean: length mismatch {len(a)} != {len(b)}"
        )
    if not a:
        raise ValueError("euclidean: empty vector")
    s = sum((float(x) - float(y)) ** 2 for x, y in zip(a, b))
    return math.sqrt(s)


__all__ = [
    "ProviderDoesNotSupportEmbedding",
    "ProviderKeyMissing",
    "ProviderUnknown",
    "cosine_similarity",
    "dot_product",
    "embed_text",
    "euclidean",
    "list_providers",
]
