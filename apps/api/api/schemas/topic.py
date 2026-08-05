"""Topic extraction schemas — TopicExtractor service contract.

The service returns ``list[str]`` (already sanitized + deduped + sorted
byte-stable), but the LLM call itself is constrained to this Pydantic
shape so a malformed response fails at the schema boundary, not at
the call site. See ADR-026 for the full design.
"""

from pydantic import BaseModel, Field


class ExtractedTopic(BaseModel):
    """One topic tag produced by the LLM.

    ``tag`` is enforced to the canonical lowercase-kebab taxonomy
    (``^[a-z0-9][a-z0-9-]{0,62}$``). The extractor normalizes upstream
    (lowercase, kebab-case, length-cap) so most candidates pass; the
    pattern is the second line of defence.
    """

    tag: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    confidence: float = Field(..., ge=0.0, le=1.0)


class TopicExtractionResult(BaseModel):
    """Wire shape between the LLM call and the sanitize/dedupe/sort step.

    The service layer validates the raw LLM response against this model
    first; on success it then runs the sanitization pipeline (lowercase
    → kebab-case → length-cap → regex → dedupe → byte-stable sort) and
    returns ``list[str]``.
    """

    topics: list[ExtractedTopic]
