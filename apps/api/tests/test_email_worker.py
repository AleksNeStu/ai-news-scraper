"""Tests for the digest email worker (Task #8, ADR-012 §12.6 + §12.7).

The worker is split into:

* ``_build_message`` — pure: returns the ``EmailMessage`` with both
  RFC 8058 headers wired in.
* ``_smtp_configured`` — pure: reads Settings, no I/O.
* ``_resolve_recipient`` — DB lookup of the recipient email by user_id.
* ``send_digest_email(payload, session)`` — async; takes the caller's
  session so the recipient resolution and the post-send delivery-status
  update happen on the same connection (ADR-012 §12.7 M2).

PII posture: assert that NEITHER the body text NOR the raw recipient
email appears in any log message; only ``recipient_hash`` + the UUIDs.
"""

from __future__ import annotations

import logging
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.config import get_settings
from api.exceptions import NotFoundError
from api.schemas.digest import EmailDigestPayload
from api.workers import email as email_worker
from api.workers.email import (
    _build_message,
    _smtp_configured,
    send_digest_email,
)


def _mock_smtp(monkeypatch: pytest.MonkeyPatch, fake: MagicMock) -> None:
    """Install a stand-in aiosmtplib.SMTP.

    The real ``aiosmtplib.SMTP`` is itself the connection — the worker's
    ``async with smtp:`` block binds ``smtp`` to the same instance and
    calls ``smtp.send_message(message)`` / ``smtp.login(...)`` on it.
    The mock has to look like that: ``__aenter__`` returns ``self``,
    and the instance carries the callables from ``fake``.
    """

    class _FakeSMTP:
        def __init__(self, *args, **kwargs):
            self.send_message = fake.send_message
            self.login = fake.login

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(email_worker.aiosmtplib, "SMTP", _FakeSMTP)


@pytest.fixture
def payload() -> EmailDigestPayload:
    """Fresh payload for each test — never reuse, since EmailMessage
    mutates its headers on insertion."""
    from uuid import uuid4

    return EmailDigestPayload(
        recipient_user_id=uuid4(),
        digest_id=uuid4(),
        for_date=date(2026, 6, 29),
        text_body="Top stories today.\n\nCoverage of cluster A.",
        html_body="<p>Top stories today.</p>",
        list_unsubscribe_url="https://briefs.example.com/unsubscribe?token=abc",
        list_unsubscribe_header=(
            "<mailto:unsubscribe@briefs.example.com>, "
            "<https://briefs.example.com/unsubscribe?token=abc>"
        ),
    )


# ---------------------------------------------------------------------------
# Message builder — pure
# ---------------------------------------------------------------------------


def test_build_message_carries_rfc8058_headers(payload: EmailDigestPayload) -> None:
    """Both ``List-Unsubscribe`` and ``List-Unsubscribe-Post`` are set."""
    msg = _build_message(
        payload,
        from_addr="briefs@example.com",
        to_addr="user@example.com",
        message_id="<digest-1@example.com>",
    )
    assert msg["List-Unsubscribe"] == payload.list_unsubscribe_header
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert msg["To"] == "user@example.com"
    assert msg["Message-ID"] == "<digest-1@example.com>"


def test_build_message_contains_text_and_html_parts(
    payload: EmailDigestPayload,
) -> None:
    """Multipart/alternative: text/plain + text/html."""
    msg = _build_message(
        payload,
        from_addr="briefs@example.com",
        to_addr="user@example.com",
        message_id="<m@example.com>",
    )
    payloads = msg.get_payload()
    assert isinstance(payloads, list) and len(payloads) >= 2
    kinds = {p.get_content_type() for p in payloads}
    assert "text/plain" in kinds
    assert "text/html" in kinds


# ---------------------------------------------------------------------------
# smtp_configured — env-driven predicate
# ---------------------------------------------------------------------------


def test_smtp_configured_false_when_host_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "smtp_host", "")
    assert _smtp_configured() is False


def test_smtp_configured_true_when_all_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(s, "smtp_port", 587)
    monkeypatch.setattr(s, "smtp_from", "briefs@example.com")
    assert _smtp_configured() is True


# ---------------------------------------------------------------------------
# send_digest_email — async, SMTP + session mocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_digest_email_returns_none_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
    payload: EmailDigestPayload,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No SMTP config → returns ``None`` and logs at INFO (no error)."""
    s = get_settings()
    monkeypatch.setattr(s, "smtp_host", "")
    caplog.set_level(logging.INFO, logger="api.workers.email")

    out = await send_digest_email(payload, session=MagicMock())
    assert out is None


@pytest.mark.asyncio
async def test_send_digest_email_does_not_log_body_or_recipient(
    monkeypatch: pytest.MonkeyPatch,
    payload: EmailDigestPayload,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PII posture (ADR-012 §12.7): no body text or raw email in any log."""
    s = get_settings()
    monkeypatch.setattr(s, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(s, "smtp_port", 587)
    monkeypatch.setattr(s, "smtp_from", "briefs@example.com")

    fake_smtp_instance = MagicMock()
    fake_smtp_instance.send_message = AsyncMock(return_value=None)
    fake_smtp_instance.login = AsyncMock(return_value=None)
    _mock_smtp(monkeypatch, fake_smtp_instance)

    async def _fake_resolve(session, user_id):
        return "user@example.com"

    monkeypatch.setattr(email_worker, "_resolve_recipient", _fake_resolve)

    # Stub out the post-send delivery update so it doesn't touch the DB.
    async def _fake_update(*args, **kwargs):
        return None

    monkeypatch.setattr(email_worker, "update_digest_delivery", _fake_update)

    caplog.set_level(logging.INFO, logger="api.workers.email")

    out = await send_digest_email(payload, session=MagicMock())
    assert out is not None  # message-id returned

    joined = "\n".join(r.getMessage() for r in caplog.records)
    for forbidden in (
        "Top stories today",  # body text
        "Coverage of cluster A",  # body text
        "user@example.com",  # raw recipient email
        "<p>Top stories today.</p>",  # html body
        payload.text_body,
        payload.html_body,
    ):
        assert forbidden not in joined, (
            f"forbidden PII substring {forbidden!r} leaked into logs: {joined!r}"
        )

    # At least one send_digest_email log was emitted.
    assert any("send_digest_email" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_send_digest_email_returns_message_id_on_success(
    monkeypatch: pytest.MonkeyPatch,
    payload: EmailDigestPayload,
) -> None:
    """Successful send returns the message-id string."""
    s = get_settings()
    monkeypatch.setattr(s, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(s, "smtp_port", 587)
    monkeypatch.setattr(s, "smtp_from", "briefs@example.com")

    fake_smtp_instance = MagicMock()
    fake_smtp_instance.send_message = AsyncMock(return_value=None)
    _mock_smtp(monkeypatch, fake_smtp_instance)

    async def _fake_resolve(session, user_id):
        return "user@example.com"

    monkeypatch.setattr(email_worker, "_resolve_recipient", _fake_resolve)

    async def _fake_update(*args, **kwargs):
        return None

    monkeypatch.setattr(email_worker, "update_digest_delivery", _fake_update)

    out = await send_digest_email(payload, session=MagicMock())
    assert out is not None
    # Message-ID format: angle-bracketed, includes @ and a domain
    assert out.startswith("<") and out.endswith(">")
    fake_smtp_instance.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_digest_email_flips_to_failed_on_missing_recipient(
    monkeypatch: pytest.MonkeyPatch,
    payload: EmailDigestPayload,
) -> None:
    """NotFoundError on resolve → worker returns ``None`` and the
    digest is flipped to ``delivery_status='failed'``."""
    s = get_settings()
    monkeypatch.setattr(s, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(s, "smtp_port", 587)
    monkeypatch.setattr(s, "smtp_from", "briefs@example.com")

    async def _missing(session, user_id):
        raise NotFoundError("no email row")

    monkeypatch.setattr(email_worker, "_resolve_recipient", _missing)

    captured: dict[str, object] = {}

    async def _capture_update(session, digest_id, **kwargs):
        captured["status"] = kwargs.get("status")
        captured["digest_id"] = digest_id

    monkeypatch.setattr(email_worker, "update_digest_delivery", _capture_update)

    out = await send_digest_email(payload, session=MagicMock())
    assert out is None
    assert captured.get("status") == "failed"
