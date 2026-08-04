"""Tests for the embedding playground router + service (Task #34 / ADR-022).

Layered tests:

* ``GET /embeddings/providers`` — auth gate, schema shape, no-key-leak
  property.
* ``POST /embeddings/embed`` — happy path, DeepSeek 422 (defence in
  depth), missing-key 422, unknown-provider 422, empty / over-length
  text 422 (Pydantic boundary).
* ``POST /embeddings/similarity`` — happy path, ``cat/kitten`` is
  higher than ``cat/dog``, length-mismatch service error path.

The provider classes are patched at the ``api.services.embeddings``
boundary (the service instantiates providers directly, not via
``get_llm_provider``, so we have to swap them at the call site). All
LLM-touching tests use a fake provider module — no network, no API
keys.

Tests assume the ``auth_user`` fixture from
``apps/api/tests/conftest.py`` exists; it mints a valid JWT for one
user and returns the headers dict used in the request bodies below.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

import api.services.embeddings as svc
from api.services.embeddings import (
    ProviderKeyMissing,
    ProviderUnknown,
    cosine_similarity,
    dot_product,
    embed_text,
    euclidean,
    list_providers,
)

# ---------------------------------------------------------------------------
# Fixtures — local module-level monkeypatching helpers
# ---------------------------------------------------------------------------


class _FakeEmbeddings:
    """Records ``embed`` calls and returns canned vectors.

    The ``embed`` coroutine returns ``[vector_a, vector_b, ...]`` so the
    service's ``vectors[0]`` indexing matches the real provider
    contract (``OpenAICompatibleProvider.embed`` /
    ``GeminiProvider.embed`` both return a list of vectors).
    """

    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[tuple[list[str], dict]] = []

    async def embed(self, texts, *, model=None):
        self.calls.append((list(texts), {"model": model}))
        return list(self.vectors)


def _patch_provider(
    monkeypatch: pytest.MonkeyPatch,
    *,
    spec_id: str,
    fake_provider: Any,
) -> None:
    """Wire ``fake_provider`` into the embeddings service for ``spec_id``.

    The service looks up providers via its own registry and
    instantiates them in-place; we intercept ``_instantiate`` so a
    single test can swap a provider without touching the registry.
    """

    def _fake_instantiate(spec, settings):
        if spec.id == spec_id:
            return fake_provider
        # Delegate to the real factory for everything else so
        # list_providers' static walk stays intact.
        return spec.cls(api_key=spec.key_resolver(settings))

    monkeypatch.setattr(svc, "_instantiate", _fake_instantiate)


# ---------------------------------------------------------------------------
# GET /embeddings/providers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_providers_requires_auth(client: AsyncClient) -> None:
    """No cookie / no bearer → 401 (ADR §22.9)."""
    resp = await client.get("/embeddings/providers")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_list_providers_shape(auth_user: dict[str, Any], client: AsyncClient) -> None:
    """Authenticated → 200; every entry has the documented fields."""
    resp = await client.get(
        "/embeddings/providers", headers=auth_user["headers"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "providers" in body
    providers = body["providers"]
    assert len(providers) >= 3  # deepseek, gemini, openrouter per ADR-011 §11.3
    required = {
        "id",
        "display_name",
        "supports_embed",
        "requires_own_key",
        "key_configured",
        "dimensions",
        "default_model",
    }
    for entry in providers:
        assert required <= set(entry.keys()), entry


@pytest.mark.asyncio
async def test_list_providers_no_key_leak(
    auth_user: dict[str, Any], client: AsyncClient
) -> None:
    """No key-like field name anywhere in the response body (ADR §22.5)."""
    resp = await client.get(
        "/embeddings/providers", headers=auth_user["headers"]
    )
    assert resp.status_code == 200
    body_str = str(resp.json()).lower()
    for forbidden in ("api_key", "apikey", "secret", "password", "token"):
        # ``token`` would also match the user's JWT — yet the JWT lives
        # only on the request, never in this response. Assert raw.
        assert forbidden not in body_str, (
            f"forbidden key-like field {forbidden!r} in response body"
        )


@pytest.mark.asyncio
async def test_list_providers_marks_deepseek_unsupported(
    auth_user: dict[str, Any], client: AsyncClient
) -> None:
    """DeepSeek entry surfaces ``supports_embed: false`` (ADR §22.4)."""
    resp = await client.get(
        "/embeddings/providers", headers=auth_user["headers"]
    )
    providers = {p["id"]: p for p in resp.json()["providers"]}
    assert "deepseek" in providers
    assert providers["deepseek"]["supports_embed"] is False
    # dimensions / default_model collapse to null when unsupported.
    assert providers["deepseek"]["dimensions"] is None
    assert providers["deepseek"]["default_model"] is None


# ---------------------------------------------------------------------------
# POST /embeddings/embed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_happy_path(
    auth_user: dict[str, Any],
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenRouter embed → 200; vector length matches ``dimensions``."""
    vec = [0.1] * 1536
    fake = _FakeEmbeddings([vec])
    _patch_provider(monkeypatch, spec_id="openrouter", fake_provider=fake)

    resp = await client.post(
        "/embeddings/embed",
        headers=auth_user["headers"],
        json={"provider_id": "openrouter", "text": "hello"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider_id"] == "openrouter"
    assert body["model"] == "openai/text-embedding-3-small"
    assert body["dimensions"] == 1536
    assert isinstance(body["vector"], list)
    assert all(isinstance(x, float) for x in body["vector"])
    assert len(body["vector"]) == 1536


@pytest.mark.asyncio
async def test_embed_deepseek_422(
    auth_user: dict[str, Any],
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defence in depth: DeepSeek request → 422
    ``provider_does_not_support_embedding`` (ADR §22.4).

    The picker hides DeepSeek by surfacing ``supports_embed: false``,
    but if a request still reaches the router we want 422, not 500.
    Setting ``deepseek_api_key`` lets the request reach the provider's
    ``embed()`` call, which raises ``NotImplementedError``; the service
    catches that and re-raises ``ProviderDoesNotSupportEmbedding``.
    """
    settings = __import__("api.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds-test")
    # Monkeypatch the underlying embed call to a NotImplementedError
    # so the test does not hit the real DeepSeek endpoint.
    import api.services.llm.deepseek as ds_module

    async def _raise_notimpl(texts, *, model=None):
        raise NotImplementedError("DeepSeek has no native embedding model")

    monkeypatch.setattr(ds_module.DeepSeekProvider, "embed", _raise_notimpl)

    resp = await client.post(
        "/embeddings/embed",
        headers=auth_user["headers"],
        json={"provider_id": "deepseek", "text": "hello"},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error_code"] == "provider_does_not_support_embedding"


@pytest.mark.asyncio
async def test_embed_key_missing_422(
    auth_user: dict[str, Any],
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider needs a key, key is empty in settings → 422
    ``provider_key_missing`` (ADR §22.5)."""
    settings = __import__("api.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    resp = await client.post(
        "/embeddings/embed",
        headers=auth_user["headers"],
        json={"provider_id": "openrouter", "text": "hello"},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error_code"] == "provider_key_missing"


@pytest.mark.asyncio
async def test_embed_unknown_provider_422(
    auth_user: dict[str, Any], client: AsyncClient
) -> None:
    """Unknown provider_id → 422 ``provider_unknown`` (ADR §22.5)."""
    resp = await client.post(
        "/embeddings/embed",
        headers=auth_user["headers"],
        json={"provider_id": "bogus", "text": "hello"},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error_code"] == "provider_unknown"


@pytest.mark.asyncio
async def test_embed_empty_text_422(
    auth_user: dict[str, Any], client: AsyncClient
) -> None:
    """``text=""`` → 422 from Pydantic (min_length=1)."""
    resp = await client.post(
        "/embeddings/embed",
        headers=auth_user["headers"],
        json={"provider_id": "openrouter", "text": ""},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_embed_too_long_text_422(
    auth_user: dict[str, Any], client: AsyncClient
) -> None:
    """``text`` length > 8000 chars → 422 from Pydantic (max_length=8000)."""
    resp = await client.post(
        "/embeddings/embed",
        headers=auth_user["headers"],
        json={"provider_id": "openrouter", "text": "x" * 8001},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# POST /embeddings/similarity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_similarity_happy_path(
    auth_user: dict[str, Any],
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two vectors → cosine + dot + euclidean present; cosine in [-1, 1]."""
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    fake = _FakeEmbeddings([a, b])
    _patch_provider(monkeypatch, spec_id="openrouter", fake_provider=fake)

    resp = await client.post(
        "/embeddings/similarity",
        headers=auth_user["headers"],
        json={
            "provider_id": "openrouter",
            "text_a": "cat",
            "text_b": "kitten",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider_id"] == "openrouter"
    assert len(body["vector_a"]) == 3
    assert len(body["vector_b"]) == 3
    assert -1.0 <= body["cosine_similarity"] <= 1.0
    # Same vector → cosine == 1.0 by definition.
    assert body["cosine_similarity"] == pytest.approx(1.0, abs=1e-6)
    assert body["dot_product"] is not None
    assert body["euclidean"] is not None


@pytest.mark.asyncio
async def test_similarity_cat_kitten_higher_than_cat_dog(
    auth_user: dict[str, Any],
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke-test the ADR §22 acceptance criterion.

    Forced pairing: ``cat/kitten`` returns cosine 1.0, ``cat/dog``
    returns cosine 0.0 (orthogonal). 1.0 > 0.0 so the comparison is
    monotone regardless of which provider is active.
    """
    cat = [1.0, 0.0, 0.0]
    kitten = [1.0, 0.0, 0.0]  # identical to cat
    dog = [0.0, 1.0, 0.0]    # orthogonal to cat

    # Sequence: first call (text_a, text_b) for cat/kitten; second for cat/dog.
    fake = _FakeEmbeddings([cat, kitten, cat, dog])
    _patch_provider(monkeypatch, spec_id="openrouter", fake_provider=fake)

    resp_ck = await client.post(
        "/embeddings/similarity",
        headers=auth_user["headers"],
        json={
            "provider_id": "openrouter",
            "text_a": "cat",
            "text_b": "kitten",
        },
    )
    assert resp_ck.status_code == 200, resp_ck.text
    cosine_ck = resp_ck.json()["cosine_similarity"]

    resp_cd = await client.post(
        "/embeddings/similarity",
        headers=auth_user["headers"],
        json={
            "provider_id": "openrouter",
            "text_a": "cat",
            "text_b": "dog",
        },
    )
    assert resp_cd.status_code == 200, resp_cd.text
    cosine_cd = resp_cd.json()["cosine_similarity"]

    assert cosine_ck > cosine_cd
    assert cosine_ck == pytest.approx(1.0, abs=1e-6)
    assert cosine_cd == pytest.approx(0.0, abs=1e-6)


@pytest.mark.asyncio
async def test_similarity_mismatched_lengths_returns_500(
    auth_user: dict[str, Any],
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider returns dim N then dim M → service raises → router 500.

    Defence: the router should NOT 422 here because the user did
    nothing wrong; the dim drift is an internal invariant break.
    """

    class _DriftyProvider:
        def __init__(self) -> None:
            self.call_count = 0

        async def embed(self, texts, *, model=None):
            self.call_count += 1
            if self.call_count == 1:
                return [[0.1] * 4]
            return [[0.1] * 5]

    monkeypatch.setattr(svc, "_instantiate", lambda spec, settings: _DriftyProvider())

    resp = await client.post(
        "/embeddings/similarity",
        headers=auth_user["headers"],
        json={
            "provider_id": "openrouter",
            "text_a": "a",
            "text_b": "b",
        },
    )
    assert resp.status_code == 500, resp.text


# ---------------------------------------------------------------------------
# Pure-math (no network, no auth)
# ---------------------------------------------------------------------------


def test_cosine_similarity_unit_vectors_match() -> None:
    """Identical unit vectors → cosine == 1.0."""
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-9)


def test_cosine_similarity_orthogonal_vectors_zero() -> None:
    """Orthogonal unit vectors → cosine == 0.0."""
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-9)


def test_cosine_similarity_length_mismatch_raises() -> None:
    """Different lengths → ``ValueError`` (500 from the router)."""
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


def test_dot_product_and_euclidean_known_values() -> None:
    """Sanity-check the bonus math primitives."""
    a = [1.0, 2.0, 3.0]
    b = [4.0, 5.0, 6.0]
    assert dot_product(a, b) == pytest.approx(32.0, abs=1e-9)
    euclid = euclidean(a, b)
    # sqrt((1-4)^2 + (2-5)^2 + (3-6)^2) = sqrt(9 + 9 + 9) = sqrt(27)
    assert euclid == pytest.approx((27.0) ** 0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# Service-level error paths (mirror the router test cases without HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_text_raises_provider_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty settings key → ``ProviderKeyMissing`` (422 in the router)."""
    settings = __import__("api.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(ProviderKeyMissing):
        await embed_text("openrouter", "hello", settings=settings)


@pytest.mark.asyncio
async def test_embed_text_raises_provider_unknown() -> None:
    """Unknown id → ``ProviderUnknown``."""
    with pytest.raises(ProviderUnknown):
        await embed_text("bogus", "hello")


def test_list_providers_service_exposes_three() -> None:
    """Direct service call without auth; count + DeepSeek flag."""
    entries = list_providers()
    ids = {p.id for p in entries}
    assert {"deepseek", "gemini", "openrouter"} <= ids
    deepseek = next(p for p in entries if p.id == "deepseek")
    assert deepseek.supports_embed is False


def test_list_providers_does_not_raise_when_provider_classes_dabbled_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider classes can be imported lazily; ``list_providers`` must
    not require SDK-side imports at the static-walk boundary.
    """
    # Default call: should not raise even in CI environments where
    # provider SDKs aren't installed (the static walk uses getattr).
    entries = list_providers()
    assert len(entries) >= 3
