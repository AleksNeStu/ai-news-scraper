"""Embedding playground router (Task #34 / ADR-022).

Three authenticated endpoints — JWT-required, per-user rate limited at
60/min per the ADR §22.6 envelope. The provider list is derived
statically from the LLM factory; embedding calls hit the same
providers the article pipeline uses. No raw API key ever crosses
this router (ADR §22.5).

Endpoints:

* ``GET  /embeddings/providers`` — list every registered provider with
  ``supports_embed`` / ``key_configured`` flags. Picker-driven UI; the
  response shape is the contract.
* ``POST /embeddings/embed`` — embed a single text against one
  provider. Returns the full vector (no truncation, ADR §22.7).
* ``POST /embeddings/similarity`` — embed two texts against the same
  provider and return the cosine (required) plus optional dot product
  and Euclidean distance. The front-end renders the comparison view
  without a second round-trip (ADR §22.3).

Failure-mode mapping (ADR §22.4 / §22.5 — never 500 for client
mistakes):

* Provider's ``embed()`` raises ``NotImplementedError`` → 422
  ``provider_does_not_support_embedding``.
* Provider needs a key and it is not configured → 422
  ``provider_key_missing``.
* ``provider_id`` does not match a registered provider → 422
  ``provider_unknown``.
* Empty / over-length text → 422 from Pydantic
  (``min_length=1`` / ``max_length=8000``).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import get_current_user_id
from api.exceptions import AppException
from api.middleware.rate_limit import rate_limit_user
from api.schemas.embeddings import (
    EmbeddingProvidersResponse,
    EmbedRequest,
    EmbedResponse,
    SimilarityRequest,
    SimilarityResponse,
)
from api.services.embeddings import (
    ProviderDoesNotSupportEmbedding,
    ProviderKeyMissing,
    ProviderUnknown,
    embed_text,
)
from api.services.embeddings import (
    cosine_similarity as _cosine_similarity,
)
from api.services.embeddings import (
    dot_product as _dot_product,
)
from api.services.embeddings import (
    euclidean as _euclidean,
)
from api.services.embeddings import (
    list_providers as _list_providers,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


# --- AppException subclasses for the three 422 codes ---------------------
# Mirrors ``apps/api/api/routers/public.py:53-66`` (ShareNotFoundError /
# ShareGoneError): AppException handler in ``api/main.py`` already
# serialises ``error_code`` into the body, so subclassing is the
# cheapest way to surface the project-specific code without forking
# ``problem_json_response``.


class ProviderDoesNotSupportEmbeddingError(AppException):
    """HTTP 422 with ``error_code = "provider_does_not_support_embedding"``."""

    status_code = 422
    error_code = "provider_does_not_support_embedding"
    title = "Provider does not support embedding"


class ProviderKeyMissingError(AppException):
    """HTTP 422 with ``error_code = "provider_key_missing"``."""

    status_code = 422
    error_code = "provider_key_missing"
    title = "Provider API key not configured"


class ProviderUnknownError(AppException):
    """HTTP 422 with ``error_code = "provider_unknown"``."""

    status_code = 422
    error_code = "provider_unknown"
    title = "Unknown embedding provider"


# --- Routes --------------------------------------------------------------


@router.get(
    "/providers",
    response_model=EmbeddingProvidersResponse,
    summary="List registered embedding providers.",
    responses={
        401: {"description": "Unauthenticated."},
    },
)
async def list_providers(
    user_id: UUID = Depends(get_current_user_id),
) -> EmbeddingProvidersResponse:
    """Enumerate every provider the LLM factory knows about.

    Auth gate is ``get_current_user_id`` (same as
    ``/articles`` / ``/scrape`` / ``/share``). The list itself is not
    a secret — three rows — but the act of issuing an embed call IS,
    so we keep the endpoint behind the JWT wall (ADR §22.9).
    """
    # user_id is required for the dependency to resolve; the provider
    # list does not depend on the identity.
    del user_id
    providers = _list_providers()
    return EmbeddingProvidersResponse.model_validate({"providers": providers})


@router.post(
    "/embed",
    response_model=EmbedResponse,
    summary="Embed a single text against one provider.",
    responses={
        401: {"description": "Unauthenticated."},
        422: {"description": "Validation, unsupported provider, or missing key."},
    },
)
async def embed(
    payload: EmbedRequest,
    user_id: UUID = Depends(get_current_user_id),
) -> EmbedResponse:
    """Embed ``payload.text`` against ``payload.provider_id``.

    Per-user rate limit at 60/min (ADR §22.6). No server-side cache
    (ADR §22.8); every call re-embeds so the user always sees the
    model's current output.
    """
    await rate_limit_user("embeddings_embed", user_id, limit=60, window_s=60)

    try:
        model, dimensions, vector = await embed_text(
            payload.provider_id,
            payload.text,
            model=payload.model,
        )
    except ProviderUnknown as exc:
        raise ProviderUnknownError(detail=str(exc)) from exc
    except ProviderKeyMissing as exc:
        raise ProviderKeyMissingError(detail=str(exc)) from exc
    except ProviderDoesNotSupportEmbedding as exc:
        raise ProviderDoesNotSupportEmbeddingError(detail=str(exc)) from exc

    return EmbedResponse(
        provider_id=payload.provider_id,
        model=model,
        dimensions=dimensions,
        vector=vector,
    )


@router.post(
    "/similarity",
    response_model=SimilarityResponse,
    summary="Embed two texts against one provider and compare them.",
    responses={
        401: {"description": "Unauthenticated."},
        422: {"description": "Validation, unsupported provider, or missing key."},
    },
)
async def similarity(
    payload: SimilarityRequest,
    user_id: UUID = Depends(get_current_user_id),
) -> SimilarityResponse:
    """Embed ``text_a`` and ``text_b`` against the same provider, then compare.

    Returns both vectors AND the cosine similarity in one round-trip
    so the front-end comparison view needs no second hop (ADR §22.3).
    Bonus fields ``dot_product`` and ``euclidean`` are surfaced when
    the math is cheap; the schema marks them ``Optional`` so the
    front-end renders 'n/a' without a hard error when absent.
    """
    await rate_limit_user("embeddings_similarity", user_id, limit=60, window_s=60)

    try:
        model_a, dims_a, vec_a = await embed_text(
            payload.provider_id, payload.text_a, model=payload.model
        )
        _model_b, dims_b, vec_b = await embed_text(
            payload.provider_id, payload.text_b, model=payload.model
        )
    except ProviderUnknown as exc:
        raise ProviderUnknownError(detail=str(exc)) from exc
    except ProviderKeyMissing as exc:
        raise ProviderKeyMissingError(detail=str(exc)) from exc
    except ProviderDoesNotSupportEmbedding as exc:
        raise ProviderDoesNotSupportEmbeddingError(detail=str(exc)) from exc

    if dims_a != dims_b:
        # Internal invariant break — two calls against the same
        # provider on the same model returned different dimensions.
        # Surface as a 500 because the user did nothing wrong.
        logger.error(
            "embedding dim drift: provider=%s model=%s dims_a=%d dims_b=%d",
            payload.provider_id,
            model_a,
            dims_a,
            dims_b,
        )
        raise AppException(
            detail="Provider returned inconsistent embedding dimensions."
        )

    return SimilarityResponse(
        provider_id=payload.provider_id,
        model=model_a,
        dimensions=dims_a,
        vector_a=vec_a,
        vector_b=vec_b,
        cosine_similarity=_cosine_similarity(vec_a, vec_b),
        dot_product=_dot_product(vec_a, vec_b),
        euclidean=_euclidean(vec_a, vec_b),
    )


__all__ = [
    "ProviderDoesNotSupportEmbeddingError",
    "ProviderKeyMissingError",
    "ProviderUnknownError",
    "router",
]
