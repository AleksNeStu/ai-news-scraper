"""Embedding playground schemas.

Task #34 / ADR-022. ``GET /embeddings/providers`` enumerates every LLM
provider the factory knows about (see ``apps/api/api/services/llm/__init__.py``
and ADR-011 §11.4), surfacing whether each one supports embeddings,
whether it needs its own key, and the native output dimension.
``POST /embeddings/embed`` re-embeds a single text against one provider;
``POST /embeddings/similarity`` does the same for two texts and returns
the cosine similarity in one round-trip.

The Pydantic models here mirror the TS types in
``packages/shared/src/types.ts`` (manual mirror — see the comment block at
the top of that file). Keep both in lock-step in the same commit or the
typecheck / pytest will fail on one side.

Three 422 codes are reserved for this surface (enforced at the router
layer; the schemas here only enforce shape):

* ``provider_does_not_support_embedding`` — the chosen provider's
  ``embed()`` raises ``NotImplementedError`` (e.g. DeepSeek,
  ``services/llm/deepseek.py:19-22``).
* ``provider_key_missing`` — the chosen provider requires its own API
  key and the key is not configured in the deployment env.
* ``provider_unknown`` — the ``provider_id`` does not match any
  registered provider in the factory.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EmbeddingProvider(BaseModel):
    """One provider entry returned by ``GET /embeddings/providers``.

    The factory at ``apps/api/api/services/llm/__init__.py`` is the source
    of truth — this schema is a serialisation contract for whatever the
    router resolves at request time. The ``key_configured`` flag is
    computed by the router from settings; the key value itself is NEVER
    placed on this model (ADR-022 §22.5).
    """

    id: str
    display_name: str
    supports_embed: bool
    requires_own_key: bool
    key_configured: bool
    dimensions: Optional[int] = None
    default_model: Optional[str] = None

    @field_validator("id", "display_name")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        # Provider id / display name are surfaced verbatim in the picker UI;
        # an empty string would render an unlabeled row.
        if not v or not v.strip():
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("dimensions")
    @classmethod
    def _dimensions_positive_when_set(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("dimensions must be positive when set")
        return v


class EmbeddingProvidersResponse(BaseModel):
    """Response body for ``GET /embeddings/providers``."""

    providers: list[EmbeddingProvider] = Field(default_factory=list)


class EmbedRequest(BaseModel):
    """Payload for ``POST /embeddings/embed``.

    The API re-embeds on every call (no server-side cache for v1,
    ADR-022 §22.8) so the user always sees a live vector from the chosen
    model — caching would defeat the "compare across providers" use case
    if a provider silently updated its model. Text is truncated server-
    side to 8000 chars (matches the existing embedder path at
    ``apps/api/api/services/embedder.py:31``).
    """

    provider_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, max_length=8000)
    model: Optional[str] = None


class EmbedResponse(BaseModel):
    """Response body for ``POST /embeddings/embed``.

    The vector is the FULL native-dimension output (ADR-022 §22.7) — no
    API-side truncation. Truncation is a display concern owned by the
    front-end, which compresses to hex + first-8-dims.
    """

    provider_id: str
    model: str
    dimensions: int
    vector: list[float]


class SimilarityRequest(BaseModel):
    """Payload for ``POST /embeddings/similarity``.

    Two texts against one provider — the comparison is always provider-
    scoped (ADR-022 §22.3). Cross-provider similarity is out of scope for
    v1; callers can hit ``/embeddings/embed`` twice and compute client-
    side.
    """

    provider_id: str = Field(..., min_length=1)
    text_a: str = Field(..., min_length=1, max_length=8000)
    text_b: str = Field(..., min_length=1, max_length=8000)
    model: Optional[str] = None


class SimilarityResponse(BaseModel):
    """Response body for ``POST /embeddings/similarity``.

    Returns both vectors AND the cosine similarity so the front-end can
    render the comparison view without a second round-trip.
    ``dot_product`` and ``euclidean`` are bonus fields (ADR-022 §22.3) —
    present when the implementation surfaces them, ``None`` otherwise.

    Cosine is the default metric because every provider in ADR-011 §11.7
    emits unit-normalised vectors, so cosine and the dot product of the
    normalised vectors are equal. Surfacing cosine only would be enough,
    but the bonus fields cost ~one float-op each at the service layer.
    """

    provider_id: str
    model: str
    dimensions: int
    vector_a: list[float]
    vector_b: list[float]
    cosine_similarity: float = Field(..., ge=-1.0, le=1.0)
    dot_product: Optional[float] = None
    euclidean: Optional[float] = None


__all__ = [
    "EmbeddingProvider",
    "EmbeddingProvidersResponse",
    "EmbedRequest",
    "EmbedResponse",
    "SimilarityRequest",
    "SimilarityResponse",
]
