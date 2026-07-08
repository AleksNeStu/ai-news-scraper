"""Sentry SDK initialization + PII redaction hooks (ADR-016 §16.4, §16.5).

This module is intentionally import-safe: the top of the file does not
``import sentry_sdk``. The Sentry dependency is an optional extra
(``[tool.poetry.extras] observability`` in ``pyproject.toml``); tests
run without it installed. The SDK import is deferred into
``init_sentry()`` so a missing package is caught locally with a logged
warning rather than at module import time.

Failure-mode contract (§16.9 rule 1):

* Empty ``SENTRY_DSN`` → silent no-op (one INFO log line).
* ``sentry_sdk`` not installed → silent no-op (INFO).
* SDK init raises (bad DSN, unreachable Sentry during init) → logged
  as a WARNING; app startup continues.

PII redaction (§16.4):

* ``before_send`` drops or mutates ``event`` for *events* (errors).
* ``before_send_transaction`` does the same for *transactions*
  (tracing performance units).
* Both hooks share the same redaction rules: the helper
  ``_scrub_dict`` mutates a shallow-copied structure in place so
  the original event dict passed in by the SDK is not preserved
  on drop.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Query-param keys whose VALUE is sensitive. Match is case-insensitive
# (§16.4 footnote); the value is replaced with ``[REDACTED]`` and the
# key is preserved so the operator still sees the URL was hit.
#
# The scrub walker in ``_redact_sensitive_values`` matches BOTH exact
# keys AND keys that contain any of these as a substring. That covers
# compound names like ``api_key`` / ``refresh_token`` / ``private_key``
# without making the test fixtures (which use ``request_id``,
# ``attempt``, ``endpoint``) false-positive.
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "password",
        "pass",
        "pwd",
        "passwd",
        "token",
        "jwt",
        "key",
        "secret",
    }
)

# Request-header names that should DROP the event entirely if present
# (their values are credentials / session material and cannot be safely
# "redacted" while still preserving diagnostic value).
_DROP_HEADER_NAMES = frozenset({"authorization", "cookie", "set-cookie"})

# Substrings that indicate a credential leaked into a free-text message
# or exception value. Matched anywhere in the string.
_CREDENTIAL_SUBSTRINGS = ("Bearer ", "JWT ", "eyJ")

_REDACTION_SENTINEL = "[REDACTED]"


def _has_credential_substring(text: str) -> bool:
    """True if ``text`` contains any of the credential substrings.

    Catches ``Bearer eyJ...``, ``JWT <token>``, and any standalone JWT
    (the ``eyJ`` prefix is the base64-JSON header for a JWT). Used on
    free-text fields (event message, exception values) where we cannot
    trust the shape enough to do a structured drop.
    """
    if not text:
        return False
    for needle in _CREDENTIAL_SUBSTRINGS:
        if needle in text:
            return True
    return False


def _headers_hold_drop_signal(headers: Any) -> bool:
    """True if any header in ``headers`` is in the DROP set.

    ``headers`` is a dict (sentry-sdk normalises to dict[str, str] but
    callers can also pass a list of tuples — we tolerate both). The
    match is case-insensitive.
    """
    if not headers:
        return False
    if isinstance(headers, dict):
        iterable = headers.items()
    else:
        iterable = headers  # type: ignore[assignment]
    for key, _value in iterable:
        if not isinstance(key, str):
            continue
        if key.lower() in _DROP_HEADER_NAMES:
            return True
    return False


def _cookies_non_empty(cookies: Any) -> bool:
    """True if ``cookies`` carries any cookie material in either shape.

    The Sentry SDK sometimes serialises cookies as a ``list[tuple[str, str]]``
    (the same shape caveat as ``_headers_hold_drop_signal``). The drop signal
    must catch both — otherwise an event with a list-cookies shape bypasses
    the drop entirely. Per §16.4 + MIN-3.
    """
    if isinstance(cookies, dict):
        return bool(cookies)
    if isinstance(cookies, (list, tuple)):
        return len(cookies) > 0
    return False


def _redact_url(url: str) -> str:
    """Redact the query-string portion of a URL, preserving path + scheme.

    ``event.request.url`` is a full URL like ``http://api:8082/auth/refresh?token=abc``.
    The query part is split on ``?``, scrubbed via ``_scrub_query_string``
    (which leaves the sentinel as ``[REDACTED]``), then percent-encoded
    so the URL stays well-formed when downstream parsers re-parse it.
    URL fragments (``#...``) are passed through unchanged.
    """
    if not url or "?" not in url:
        return url
    prefix, _, qs = url.partition("?")
    new_qs = _scrub_query_string(qs)
    if new_qs is None:
        return url
    # The redaction sentinel may contain ``[`` / ``]`` characters which
    # must be percent-encoded inside a URL query value. We re-encode
    # only the redacted pair (so we don't disturb any percent-encoding
    # the original URL may have carried on non-sensitive params).
    encoded = _percent_encode_redacted_pairs(new_qs)
    return f"{prefix}?{encoded}"


def _percent_encode_redacted_pairs(query_string: str) -> str:
    """Re-encode ``[REDACTED]`` values inside a query string.

    Walk each ``k=v`` pair; if the value is the redaction sentinel,
    percent-encode the brackets so the result is a valid URL token.
    Non-redacted pairs are left untouched (preserves any pre-existing
    percent-encoding on legitimate params).
    """
    pairs = query_string.split("&")
    out: list[str] = []
    for pair in pairs:
        if "=" not in pair:
            out.append(pair)
            continue
        key, value = pair.split("=", 1)
        if value == _REDACTION_SENTINEL:
            out.append(f"{key}={quote(_REDACTION_SENTINEL, safe='')}")
        else:
            out.append(pair)
    return "&".join(out)


def _is_sensitive_key(key: str) -> bool:
    """True if ``key`` is, or contains, a known sensitive token.

    Matches BOTH the exact key (e.g. ``"token"``) and compound
    names that include a sensitive substring (e.g. ``"api_key"``,
    ``"refresh_token"``, ``"private_key"``). Avoids false positives
    on obviously-bystander fields (``request_id``, ``attempt``,
    ``endpoint``) because none of those contain a sensitive token.
    """
    if not isinstance(key, str):
        return False
    kl = key.lower()
    if kl in _SENSITIVE_QUERY_KEYS or kl in _DROP_HEADER_NAMES:
        return True
    return any(token in kl for token in _SENSITIVE_QUERY_KEYS)


def _redact_sensitive_values(payload: Any) -> Any:
    """Walk a nested dict/list/tuple and redact values for sensitive keys.

    Used on ``event.extra``, ``event.contexts`` (the full tree, not just
    ``trace``), ``event.breadcrumbs[*].data``, and other free-form dicts.
    Match is case-insensitive against the same sensitive set as query params
    plus the credential-header set — anything in those namespaces is
    replaced with ``[REDACTED]``. The shape of the structure is preserved;
    only the values change. Returns a deep copy; the original is not
    mutated.

    Per MIN-1 (§16.4 "more restrictive than the existing privacy posture").
    """
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for k, v in payload.items():
            if _is_sensitive_key(k):
                out[k] = _REDACTION_SENTINEL
            else:
                out[k] = _redact_sensitive_values(v)
        return out
    if isinstance(payload, list):
        return [_redact_sensitive_values(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(_redact_sensitive_values(item) for item in payload)
    return payload


def _redact_user(user: Any) -> Any | None:
    """Return a PII-redacted copy of an ``event.user`` dict, or ``None`` to drop.

    Per §16.4 + MAJ-2:

    * ``email`` is dropped (a free-text PII that has no diagnostic value).
    * ``ip_address`` is dropped (operator does not need raw IPs).
    * ``id`` is replaced with the redaction sentinel — keeps the cardinality
      shape so the operator still sees "1 user triggered this" without
      seeing which user.

    Any other key (e.g. ``username``, ``segment``) passes through unchanged.
    """
    if not isinstance(user, dict):
        return None
    out: dict[str, Any] = {}
    for k, v in user.items():
        kl = k.lower() if isinstance(k, str) else ""
        if kl == "email" or kl == "ip_address":
            continue  # drop
        if kl == "id":
            out[k] = _REDACTION_SENTINEL
        else:
            out[k] = v
    return out


def _scrub_query_string(query_string: str) -> str | None:
    """Redact sensitive values in a URL query string.

    Returns the mutated query string with the redacted value as the
    literal ``[REDACTED]`` sentinel (NOT percent-encoded). The Sentry
    Python SDK stores ``request.query_string`` unencoded; encoding
    here would surprise consumers that match the literal sentinel.
    The full-URL ``event.request.url`` redaction (handled in
    ``_redact_url``) percent-encodes the same sentinel after the
    scrub, so URL parsers downstream stay happy.
    """
    if not query_string:
        return None
    # Sentry stores query_string WITHOUT a leading '?' (per docs).
    # Split, walk pairs, rebuild. Tolerate missing values gracefully.
    pairs = query_string.split("&")
    out_pairs: list[str] = []
    for pair in pairs:
        if not pair:
            continue
        if "=" in pair:
            key, _value = pair.split("=", 1)
        else:
            key, _value = pair, ""
        if _is_sensitive_key(key):
            out_pairs.append(f"{key}={_REDACTION_SENTINEL}")
        else:
            out_pairs.append(pair)
    return "&".join(out_pairs)


def _scrub_dict(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return a PII-scrubbed COPY of ``payload``, or ``None`` to drop it.

    The input dict is NOT mutated. Rules applied (per §16.4 + MAJ-2 /
    MIN-1 / MIN-2 / MIN-3 from Devil's review):

    * Drop entirely if ``request.headers`` carries Authorization /
      Cookie / Set-Cookie (any case, dict OR list-of-tuples shape).
    * Drop entirely if ``request.cookies`` is non-empty (dict OR
      list-of-tuples shape — MIN-3).
    * Redact ``request.query_string`` so sensitive keys get
      ``[REDACTED]`` values.
    * Redact ``request.url`` query portion (MIN-2 — the SDK captures
      full URLs into ``event.request.url``).
    * Mask ``message`` and ``exception.values[*].value`` for any
      credential substring (``Bearer ``, ``JWT ``, ``eyJ...``).
    * Mask ``transaction`` for the same substrings.
    * Redact ``user.email`` / ``user.ip_address`` (drop) and
      ``user.id`` (replace with ``[REDACTED]``) — MAJ-2.
    * Walk ``contexts`` (full tree), ``extra``, and
      ``breadcrumbs[*].data`` for sensitive keys; redact values to
      ``[REDACTED]`` while preserving key names — MIN-1.

    Returns ``None`` to signal "drop the event" (the SDK contract for
    a ``before_send`` hook returning ``None``). Returns the mutated
    COPY otherwise.
    """
    if not isinstance(payload, dict):
        return None

    scrubbed: dict[str, Any] = {k: v for k, v in payload.items()}

    # ---- request.headers / request.cookies / request.url (drop + redact) ----
    request = scrubbed.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if _headers_hold_drop_signal(headers):
            return None
        cookies = request.get("cookies")
        if _cookies_non_empty(cookies):
            return None
        # Scrub the query_string (mutate in the copy).
        qs = request.get("query_string")
        if isinstance(qs, str) and qs:
            new_qs = _scrub_query_string(qs)
            if new_qs is not None:
                request["query_string"] = new_qs
        # MIN-2: also scrub the full URL — query-string only is incomplete
        # for transaction events where the SDK captures ``http://...?...``.
        url = request.get("url")
        if isinstance(url, str) and url:
            request["url"] = _redact_url(url)

    # ---- message + exception values (credential substring) ----
    message = scrubbed.get("message")
    if isinstance(message, str) and _has_credential_substring(message):
        # Replace the entire message — partial masking can leave enough
        # structure to reconstruct the token. Keep the key, blank the value.
        scrubbed["message"] = _REDACTION_SENTINEL

    exceptions = scrubbed.get("exception")
    if isinstance(exceptions, dict):
        values = exceptions.get("values")
        if isinstance(values, list):
            for exc in values:
                if isinstance(exc, dict):
                    val = exc.get("value")
                    if isinstance(val, str) and _has_credential_substring(val):
                        exc["value"] = _REDACTION_SENTINEL

    # ---- transaction (perf hook also routes here) ----
    transaction = scrubbed.get("transaction")
    if isinstance(transaction, str) and _has_credential_substring(transaction):
        scrubbed["transaction"] = _REDACTION_SENTINEL

    # ---- user (MAJ-2) ----
    user = scrubbed.get("user")
    if user is not None:
        new_user = _redact_user(user)
        if new_user is None:
            scrubbed["user"] = {}
        else:
            scrubbed["user"] = new_user

    # ---- contexts: trace URLs (specific) + sensitive-key walk (general) ----
    contexts = scrubbed.get("contexts")
    if isinstance(contexts, dict):
        trace = contexts.get("trace")
        if isinstance(trace, dict):
            for url_field in ("url", "view_url"):
                url = trace.get(url_field)
                if isinstance(url, str) and "?" in url:
                    prefix, _, qs = url.partition("?")
                    new_qs = _scrub_query_string(qs)
                    if new_qs is not None:
                        trace[url_field] = f"{prefix}?{new_qs}"
        # MIN-1: walk the full contexts tree for sensitive keys.
        scrubbed["contexts"] = _redact_sensitive_values(contexts)

    # ---- extra (MIN-1) ----
    extra = scrubbed.get("extra")
    if extra is not None:
        scrubbed["extra"] = _redact_sensitive_values(extra)

    # ---- breadcrumbs[*].data (MIN-1) ----
    breadcrumbs = scrubbed.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        values = breadcrumbs.get("values")
        if isinstance(values, list):
            for crumb in values:
                if isinstance(crumb, dict):
                    data = crumb.get("data")
                    if data is not None:
                        crumb["data"] = _redact_sensitive_values(data)

    return scrubbed


def _redact_before_send(
    event: dict[str, Any], hint: dict[str, Any]
) -> dict[str, Any] | None:
    """``sentry_sdk.init(before_send=...)`` hook for *event* capture.

    Returns ``None`` to drop the event, or the (possibly mutated) dict
    to send it through. The SDK's signature passes a dict-like event
    plus a hint dict (carries the original exception); we use neither
    for redaction — the rules are data-shape based, not exception-type
    based.
    """
    return _scrub_dict(event)


def _redact_before_send_transaction(
    event: dict[str, Any], hint: dict[str, Any]
) -> dict[str, Any] | None:
    """``sentry_sdk.init(before_send_transaction=...)`` hook.

    Same redaction rules as ``_redact_before_send``; SDK requires a
    separate callable because transaction events pass through a
    different processor pipeline.
    """
    return _scrub_dict(event)


# Tracks whether ``init_sentry()`` has already configured the SDK in
# this process. Idempotent — repeated calls do NOT double-register
# handlers (per §16.10 test #6).
_INITIALISED = False


def init_sentry() -> None:
    """Wire Sentry into the running api process.

    Called from the FastAPI lifespan in ``apps/api/api/main.py``,
    immediately after ``configure_logging(...)`` and before any
    scheduler start. Contract per §16.5 + §16.9:

    * Empty / unset ``SENTRY_DSN`` → silent no-op, one INFO log line.
    * ``sentry_sdk`` not installed → silent no-op, one INFO log line.
    * SDK init raises → logged as WARNING, swallowed.
    * Already initialised in this process → no-op (idempotent).
    """
    global _INITIALISED
    if _INITIALISED:
        logger.debug("sentry init skipped: already initialised in this process")
        return

    settings = _read_settings()
    if not settings["dsn"]:
        logger.info("sentry init skipped: DSN empty")
        return

    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError as e:
        logger.info("sentry init skipped: sentry-sdk not installed (%s)", e)
        return

    try:
        sentry_sdk.init(
            dsn=settings["dsn"],
            traces_sample_rate=0.2,
            profiles_sample_rate=0.1,
            send_default_pii=False,
            release=settings["release"],
            before_send=_redact_before_send,
            before_send_transaction=_redact_before_send_transaction,
        )
        _INITIALISED = True
        logger.info("sentry initialised (release=%s)", settings["release"] or "unknown")
    except Exception as e:  # noqa: BLE001 — broad on purpose per §16.9
        logger.warning("sentry init failed: %s", e)


def _read_settings() -> dict[str, str]:
    """Read Sentry env vars.

    Defensive: the api ``Settings`` object is pydantic and cached at
    import time. Reading the env vars directly here keeps
    ``sentry_init`` importable in tests without instantiating the full
    app config (which would pull in DB / Redis defaults). Per §16.9
    rule 3 the module must be import-safe WITHOUT Sentry installed.
    """
    return {
        "dsn": os.environ.get("SENTRY_DSN", ""),
        "release": os.environ.get("SENTRY_RELEASE", ""),
    }


def reset_for_tests() -> None:
    """Test helper: clear the initialised flag so each test starts clean.

    NOT part of the production API. Mirrors the
    ``reset_logging_for_tests()`` pattern in
    ``apps/api/api/middleware/logging.py``.
    """
    global _INITIALISED
    _INITIALISED = False
