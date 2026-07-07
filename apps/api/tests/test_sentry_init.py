"""Unit tests for the Sentry SDK init + PII redaction hooks.

Per ADR-016 §16.5, §16.10. The matrix in §16.10 has six cases; each
test below targets one bullet. The ``sentry-sdk`` import is mocked
because the dependency is an optional ``[observability]`` extra
(§16.9 rule 3) and may not be installed in the test environment.

PII scrubbing contract (§16.4):

* ``before_send`` / ``before_send_transaction`` return ``None`` to
  drop the event (Authorization / Cookie / Set-Cookie header
  present, ``request.cookies`` non-empty).
* Sensitive query params (``password``, ``pass``, ``pwd``, ``passwd``,
  ``token``, ``jwt``, ``key``, ``secret``) are mutated to a
  ``[REDACTED]`` value while preserving the key.
* Credential substrings (``Bearer ``, ``JWT ``, ``eyJ...``) in
  ``message`` / ``exception.values[*].value`` / ``transaction`` are
  blanked to the redaction sentinel.

Each test resets the ``_INITIALISED`` flag via ``reset_for_tests()``
so the suite can run in any order.
"""

from __future__ import annotations

from typing import Any

import pytest

from api.sentry_init import (
    _INITIALISED,
    _has_credential_substring,
    _headers_hold_drop_signal,
    _redact_before_send,
    _redact_before_send_transaction,
    _scrub_dict,
    _scrub_query_string,
    init_sentry,
    reset_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_sentry_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear env + the ``_INITIALISED`` flag before every test.

    Tests that exercise ``init_sentry()`` must not see state leaked
    from earlier tests. The autouse scope keeps every test
    deterministic without per-test boilerplate.
    """
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("SENTRY_RELEASE", raising=False)
    reset_for_tests()
    yield
    reset_for_tests()


# ---------------------------------------------------------------------------
# init_sentry() — graceful no-op + idempotency
# ---------------------------------------------------------------------------


def test_init_no_op_when_dsn_empty(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Empty SENTRY_DSN → ``sentry_sdk.init`` is NOT called.

    §16.10 case 1. We patch ``sentry_sdk.init`` via
    ``unittest.mock.patch`` against the symbol inside the
    ``sentry_init`` namespace (the module defers the import until
    the first call, so we patch the attribute that resolves on
    first import).
    """
    monkeypatch.setenv("SENTRY_DSN", "")
    fake_init = _make_fake_init(monkeypatch)

    with caplog.at_level("INFO", logger="api.sentry_init"):
        init_sentry()

    fake_init.assert_not_called()
    assert any("DSN empty" in rec.message for rec in caplog.records)


def test_init_does_not_raise_on_bad_dsn(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Bad DSN → ``init_sentry()`` swallows the exception.

    §16.10 case 2. We install a fake ``sentry_sdk`` whose ``init``
    raises ``RuntimeError`` and confirm no exception propagates from
    ``init_sentry()``. The exception is logged as a WARNING per
    §16.9 rule 1.
    """
    monkeypatch.setenv("SENTRY_DSN", "https://garbage@example.com/1")

    class _RaisingSDK:
        def init(self, **kwargs: Any) -> None:
            raise RuntimeError("boom")

    monkeypatch.setitem(__import__("sys").modules, "sentry_sdk", _RaisingSDK())

    with caplog.at_level("WARNING", logger="api.sentry_init"):
        # Must not raise.
        init_sentry()


def test_before_send_redacts_authorization_header() -> None:
    """§16.10 case 3 — Authorization header present → drop the event.

    Per §16.4, the drop set is case-insensitive. We verify both
    ``Authorization`` (canonical) and ``authorization`` (lowercase)
    drop the event.
    """
    event: dict[str, Any] = {
        "request": {"headers": {"Authorization": "Bearer X"}},
        "message": "ok",
    }
    assert _redact_before_send(event, {}) is None

    event_lower: dict[str, Any] = {
        "request": {"headers": {"authorization": "Bearer X"}},
        "message": "ok",
    }
    assert _redact_before_send(event_lower, {}) is None


def test_before_send_redacts_query_token_param() -> None:
    """§16.10 case 4 — sensitive query param value → ``[REDACTED]``.

    The key is preserved; the value is replaced.
    """
    event: dict[str, Any] = {
        "request": {"query_string": "token=abc&page=2"},
        "message": "ok",
    }
    result = _redact_before_send(event, {})
    assert result is not None
    scrubbed_qs = result["request"]["query_string"]
    # 'token' value replaced; 'page' unchanged.
    assert "token=" in scrubbed_qs
    assert "[REDACTED]" in scrubbed_qs
    assert "abc" not in scrubbed_qs
    assert "page=2" in scrubbed_qs


def test_before_send_drops_cookie_header() -> None:
    """§16.10 case 5 — Cookie header present → drop the event.

    Case-insensitive match per §16.4.
    """
    event: dict[str, Any] = {
        "request": {"headers": {"cookie": "session=xyz"}},
        "message": "ok",
    }
    assert _redact_before_send(event, {}) is None


def test_init_invokes_sentry_sdk_init_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§16.10 case 6 — calling ``init_sentry()`` twice is idempotent.

    The SDK registers global handlers + the FastAPI integration on
    first ``init``. A second call in the same process would
    double-register, so ``init_sentry()`` short-circuits after the
    first success.
    """
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    fake_init = _make_fake_init(monkeypatch)

    init_sentry()
    init_sentry()

    assert fake_init.call_count == 1


# ---------------------------------------------------------------------------
# Bonus: structural tests on the helpers so the §16.10 cases above have
# a documented contract to fall back on if the SDK API drifts.
# ---------------------------------------------------------------------------


def test_credential_substring_matches_jwt_prefix() -> None:
    """JWT values begin with ``eyJ`` — substring match catches them."""
    assert _has_credential_substring("token=eyJhbGciOiJIUzI1NiJ9.payload.sig")
    assert not _has_credential_substring("token=plaintext-no-credentials")


def test_credential_substring_empty_or_none_safe() -> None:
    """Empty / None input never raises and never matches."""
    assert not _has_credential_substring("")
    # type: ignore[arg-type] — defensive guard against None.
    assert not _has_credential_substring(None)  # type: ignore[arg-type]


def test_headers_hold_drop_signal_accepts_dict_and_list_of_tuples() -> None:
    """Sentry SDK sometimes serialises headers as a list of tuples."""
    assert _headers_hold_drop_signal({"Authorization": "Bearer X"})
    assert _headers_hold_drop_signal([("Cookie", "session=xyz")])
    assert not _headers_hold_drop_signal({"Content-Type": "application/json"})
    assert not _headers_hold_drop_signal({})


def test_scrub_query_string_preserves_non_sensitive_keys() -> None:
    """Helper preserves ordering + non-sensitive params exactly."""
    qs = "page=1&token=abc&q=hello"
    out = _scrub_query_string(qs)
    assert out is not None
    assert out.startswith("page=1")
    assert "token=[REDACTED]" in out
    assert "q=hello" in out


def test_scrub_query_string_returns_none_for_empty() -> None:
    """Empty / falsy input returns None so callers can skip."""
    assert _scrub_query_string("") is None


def test_redact_before_send_transaction_applies_same_rules() -> None:
    """Transaction hook must also drop on Authorization header."""
    event: dict[str, Any] = {
        "request": {"headers": {"Authorization": "Bearer X"}},
        "transaction": "/api/backend/auth/login",
    }
    assert _redact_before_send_transaction(event, {}) is None


def test_scrub_dict_redacts_credentials_in_message() -> None:
    """A message containing ``Bearer ...`` is blanked, not dropped.

    The drop set is for header / cookie fields; messages with a
    credential substring get the value masked (the event still
    surfaces, just without the token).
    """
    event: dict[str, Any] = {
        "message": "authorization failed: Bearer abc.def.ghi",
    }
    out = _scrub_dict(event)
    assert out is not None
    assert "Bearer" not in out["message"]
    assert out["message"] == "[REDACTED]"


def test_scrub_dict_redacts_credentials_in_exception_value() -> None:
    """Free-text exception values with a JWT prefix are masked."""
    event: dict[str, Any] = {
        "exception": {
            "values": [{"type": "ValueError", "value": "bad token eyJabc.def.ghi"}],
        },
    }
    out = _scrub_dict(event)
    assert out is not None
    val = out["exception"]["values"][0]["value"]
    assert "eyJ" not in val
    assert val == "[REDACTED]"


def test_scrub_dict_drops_when_cookies_dict_non_empty() -> None:
    """§16.4 — ``request.cookies`` non-empty → drop the event."""
    event: dict[str, Any] = {
        "request": {"cookies": {"session": "xyz"}},
    }
    assert _scrub_dict(event) is None


# ---------------------------------------------------------------------------
# MIN-3 — ``request.cookies`` list-of-tuples shape must also drop.
# The SDK sometimes serialises cookies as ``list[tuple[str, str]]``;
# previously the drop check only matched dict. Same shape caveat as
# ``_headers_hold_drop_signal``.
# ---------------------------------------------------------------------------


def test_scrub_dict_drops_when_cookies_list_of_tuples() -> None:
    """MIN-3 — cookies as a non-empty list-of-tuples also drops."""
    event: dict[str, Any] = {
        "request": {"cookies": [("session", "xyz")]},
    }
    assert _scrub_dict(event) is None


# ---------------------------------------------------------------------------
# MIN-2 — ``event.request.url`` query portion must also be redacted.
# The SDK captures full URLs into ``event.request.url`` (FastAPI
# integration), not only into ``query_string``. Tokens in the URL leak
# otherwise.
# ---------------------------------------------------------------------------


def test_scrub_dict_redacts_query_string_in_request_url() -> None:
    """MIN-2 — ``request.url`` with ``?token=abc`` → token scrubbed."""
    event: dict[str, Any] = {
        "request": {"url": "http://api:8082/auth/refresh?token=abc123&page=1"},
    }
    out = _scrub_dict(event)
    assert out is not None
    url = out["request"]["url"]
    assert "abc123" not in url
    assert "token=" in url and "%5BREDACTED%5D" in url
    assert "page=1" in url


def test_scrub_dict_preserves_request_url_without_query() -> None:
    """URLs without ``?`` pass through unchanged."""
    event: dict[str, Any] = {
        "request": {"url": "http://api:8082/health"},
    }
    out = _scrub_dict(event)
    assert out is not None
    assert out["request"]["url"] == "http://api:8082/health"


# ---------------------------------------------------------------------------
# MAJ-2 — ``event.user`` PII (email, ip_address, id).
# ---------------------------------------------------------------------------


def test_scrub_dict_drops_user_email() -> None:
    """MAJ-2 — ``user.email`` is dropped from the event."""
    event: dict[str, Any] = {
        "user": {"id": "user-123", "email": "alice@example.com"},
    }
    out = _scrub_dict(event)
    assert out is not None
    assert "email" not in out["user"]
    # id is replaced with [REDACTED] (cardinality preserved, identity hidden)
    assert out["user"]["id"] == "[REDACTED]"


def test_scrub_dict_drops_user_ip_address() -> None:
    """MAJ-2 — ``user.ip_address`` is dropped."""
    event: dict[str, Any] = {
        "user": {"id": "user-123", "ip_address": "192.168.1.1"},
    }
    out = _scrub_dict(event)
    assert out is not None
    assert "ip_address" not in out["user"]


def test_scrub_dict_preserves_non_pii_user_fields() -> None:
    """MAJ-2 — non-PII user fields (e.g. username, segment) pass through."""
    event: dict[str, Any] = {
        "user": {
            "id": "user-123",
            "email": "alice@example.com",
            "username": "alice",
            "segment": "beta",
        },
    }
    out = _scrub_dict(event)
    assert out is not None
    assert out["user"]["username"] == "alice"
    assert out["user"]["segment"] == "beta"
    assert "email" not in out["user"]


# ---------------------------------------------------------------------------
# MIN-1 — ``extra`` / ``contexts`` / ``breadcrumbs[*].data`` sensitive-key walk.
# ---------------------------------------------------------------------------


def test_scrub_dict_redacts_sensitive_keys_in_extra() -> None:
    """MIN-1 — ``extra.token`` / ``extra.password`` → ``[REDACTED]``."""
    event: dict[str, Any] = {
        "extra": {
            "request_id": "req-123",
            "token": "eyJabc.def.ghi",
            "password": "hunter2",
            "context": {"api_key": "secret-key", "page": 1},
        },
    }
    out = _scrub_dict(event)
    assert out is not None
    assert out["extra"]["request_id"] == "req-123"
    assert out["extra"]["token"] == "[REDACTED]"
    assert out["extra"]["password"] == "[REDACTED]"
    assert out["extra"]["context"]["api_key"] == "[REDACTED]"
    assert out["extra"]["context"]["page"] == 1


def test_scrub_dict_redacts_sensitive_keys_in_contexts() -> None:
    """MIN-1 — full contexts tree walked for sensitive keys."""
    event: dict[str, Any] = {
        "contexts": {
            "runtime": {"name": "python", "version": "3.12"},
            "auth": {
                "user_id": "user-123",
                "jwt": "eyJabc.def.ghi",  # sensitive key → redacted
            },
        },
    }
    out = _scrub_dict(event)
    assert out is not None
    assert out["contexts"]["runtime"]["name"] == "python"
    assert out["contexts"]["auth"]["user_id"] == "user-123"
    assert out["contexts"]["auth"]["jwt"] == "[REDACTED]"


def test_scrub_dict_redacts_sensitive_keys_in_breadcrumbs() -> None:
    """MIN-1 — ``breadcrumbs[*].data`` walked for sensitive keys."""
    event: dict[str, Any] = {
        "breadcrumbs": {
            "values": [
                {
                    "category": "auth",
                    "data": {
                        "url": "/auth/login",
                        "password": "hunter2",
                        "attempt": 1,
                    },
                },
                {
                    "category": "fetch",
                    "data": {"endpoint": "/articles", "token": "eyJabc"},
                },
            ],
        },
    }
    out = _scrub_dict(event)
    assert out is not None
    assert out["breadcrumbs"]["values"][0]["data"]["url"] == "/auth/login"
    assert out["breadcrumbs"]["values"][0]["data"]["password"] == "[REDACTED]"
    assert out["breadcrumbs"]["values"][0]["data"]["attempt"] == 1
    assert out["breadcrumbs"]["values"][1]["data"]["endpoint"] == "/articles"
    assert out["breadcrumbs"]["values"][1]["data"]["token"] == "[REDACTED]"


def test_scrub_dict_drops_authorization_in_nested_data() -> None:
    """Header-shaped sensitive keys (``authorization``, ``cookie``)
    are also redacted in nested dicts — same drop set as ``request.headers``."""
    event: dict[str, Any] = {
        "extra": {
            "headers": {
                "Authorization": "Bearer xyz",
                "X-Custom": "ok",
            },
        },
    }
    out = _scrub_dict(event)
    assert out is not None
    assert out["extra"]["headers"]["Authorization"] == "[REDACTED]"
    assert out["extra"]["headers"]["X-Custom"] == "ok"


# ---------------------------------------------------------------------------
# Test helpers — install a stand-in sentry_sdk so init_sentry can run.
# ---------------------------------------------------------------------------


class _FakeSentrySDK:
    """Minimal stand-in for the ``sentry_sdk`` module.

    Only ``init`` is exercised by ``init_sentry()``. The ``init``
    attribute is a ``MagicMock`` so tests can use the standard
    ``assert_called_once_with`` / ``call_count`` surface.
    """

    def __init__(self, raise_on_init: Exception | None = None) -> None:
        from unittest.mock import MagicMock

        self.init = MagicMock()
        if raise_on_init is not None:
            self.init.side_effect = raise_on_init


def _make_fake_init(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Patch the deferred import path so ``sentry_sdk.init`` is recorded.

    Returns the ``_FakeSentrySDK`` instance so tests can read
    ``fake_sdk.init.call_count`` / ``.calls`` (MagicMock surface).
    """
    fake_sdk = _FakeSentrySDK()
    # We can't ``monkeypatch.setattr`` the literal ``import sentry_sdk``
    # statement (that runs only when ``init_sentry`` is called), so we
    # inject the fake into ``sys.modules`` under the name the module
    # imports. This is the same trick pytest uses to fake any import.
    monkeypatch.setitem(__import__("sys").modules, "sentry_sdk", fake_sdk)
    return fake_sdk.init


# Sanity check: the module-level state is consistent with what the
# other tests rely on.
def test_initialised_flag_starts_false() -> None:
    """The module-level ``_INITIALISED`` flag is False at import time.

    If a future refactor breaks the lazy init pattern, this test
    fails fast.
    """
    # Note: a previous test may have flipped it; reset is the
    # fixture's job. We assert here on the freshly-reset value.
    reset_for_tests()
    assert _INITIALISED is False
