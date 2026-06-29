"""SMTP email worker for AI Brief digests (Task #8, ADR-012 §12.6).

Public surface: ``send_digest_email(payload, session) -> message_id``.

* Transport: ``aiosmtplib`` for the async send, with graceful
  degradation when SMTP env vars are absent (log + return ``None`` so
  the caller can mark the digest ``delivery_status='notified'``).
* Envelope: ``multipart/alternative`` with text + HTML bodies.
* RFC 8058 one-click unsubscribe headers:
    ``List-Unsubscribe`` + ``List-Unsubscribe-Post: List-Unsubscribe=One-Click``
* PII posture (ADR-012 §12.7, M2 fix): the raw recipient email is
  resolved server-side inside this module via the passed-in ``session``.
  The worker takes the ``AsyncSession`` from the caller (NOT opens its
  own) so the resolution and the post-send ``update_digest_delivery``
  happen on the same connection. Retry queues / log lines / exception
  tracebacks therefore cannot leak the raw address.
* After success / failure, calls ``update_digest_delivery`` so the
  digest row's ``delivery_status`` + ``email_message_id`` actually
  reflect reality (m9 / m14 — Devil Round 2).
* No body text in logs; allowed log fields are ``digest_id``,
  ``recipient_user_id``, ``message_id``, ``recipient_hash``.
* ``smtp_from`` split is defensive — falls back to ``localhost`` when
  the address has no ``@`` (n6).

This module deliberately has NO FastAPI imports — it's a pure worker
the router / scheduler calls after the digest row is persisted.
"""

from __future__ import annotations

import hashlib
import logging
from email.message import EmailMessage
from email.utils import make_msgid
from uuid import UUID

import aiosmtplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.exceptions import NotFoundError
from api.models.user import User
from api.schemas.digest import EmailDigestPayload
from api.services.digest import update_digest_delivery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Body builders
# ---------------------------------------------------------------------------


def _text_body(payload: EmailDigestPayload) -> str:
    """Plain-text alt body (RFC 8058 mandates a text version)."""
    return (
        "Your daily brief is ready.\n\n"
        f"{payload.text_body}\n\n"
        "Unsubscribe: "
        f"{payload.list_unsubscribe_url}\n"
    )


def _html_body(payload: EmailDigestPayload) -> str:
    """Minimal HTML alt body. Production-quality design is out of v1 scope."""
    safe_summary = (
        payload.text_body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        "<html><body>"
        "<h1>Your daily brief is ready</h1>"
        f'<pre style="font-family:system-ui">{safe_summary}</pre>'
        "<hr>"
        f'<p><a href="{payload.list_unsubscribe_url}">Unsubscribe</a></p>'
        "</body></html>"
    )


def _build_message(
    payload: EmailDigestPayload,
    *,
    from_addr: str,
    to_addr: str,
    message_id: str,
) -> EmailMessage:
    """Construct the RFC 5322 + 8058 envelope."""
    msg = EmailMessage()
    msg["Subject"] = "Your daily AI news brief"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Message-ID"] = message_id
    msg["List-Unsubscribe"] = payload.list_unsubscribe_header
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(_text_body(payload))
    msg.add_alternative(_html_body(payload), subtype="html")
    return msg


# ---------------------------------------------------------------------------
# SMTP config helpers
# ---------------------------------------------------------------------------


def _smtp_configured() -> bool:
    """True iff the SMTP env vars needed for a real send are present."""
    s = get_settings()
    return bool(s.smtp_host and s.smtp_port and s.smtp_from)


def _smtp_domain() -> str:
    """Defensive (n6): extract the message-id domain from ``SMTP_FROM``.

    Falls back to ``"localhost"`` when the address has no ``@``
    (e.g. ``smtp_from = "briefs"``).
    """
    s = get_settings()
    if "@" in s.smtp_from:
        return s.smtp_from.split("@", 1)[1] or "localhost"
    return "localhost"


async def _resolve_recipient(session: AsyncSession, user_id: UUID) -> str:
    """Look up the recipient address server-side (M2 — PII boundary).

    Raises ``NotFoundError`` if the user has no email row. The caller
    catches that and flips the digest to ``delivery_status='failed'``.
    """
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None or not user.email:
        raise NotFoundError(f"user {user_id} not found or has no email")
    return user.email


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def send_digest_email(
    payload: EmailDigestPayload, session: AsyncSession
) -> str | None:
    """Send the digest via SMTP. Returns the RFC 5322 ``Message-Id`` or
    ``None`` if delivery was skipped / failed.

    M2 fix: the worker takes ``session`` from the caller and resolves
    the recipient email server-side. The payload carries only the opaque
    ``recipient_user_id``; raw PII never crosses the worker→transport
    boundary.

    m9 fix: after success, flips the digest to ``delivery_status='emailed'``
    via ``update_digest_delivery`` with the message-id. After failure,
    flips to ``'failed'``. After "SMTP unconfigured", leaves the row
    alone — the digest stays ``'notified'`` (in-app only).
    """
    s = get_settings()

    if not _smtp_configured():
        logger.info(
            "send_digest_email: SMTP not configured, skipping",
            extra={
                "digest_id": str(payload.digest_id),
                "recipient_user_id": str(payload.recipient_user_id),
            },
        )
        return None

    # Resolve the email server-side; the payload carries only the ID.
    try:
        recipient_email = await _resolve_recipient(session, payload.recipient_user_id)
    except NotFoundError:
        logger.warning(
            "send_digest_email: recipient not found",
            extra={
                "digest_id": str(payload.digest_id),
                "recipient_user_id": str(payload.recipient_user_id),
            },
        )
        await update_digest_delivery(session, payload.digest_id, status="failed")
        return None

    recipient_hash = hashlib.sha256(recipient_email.encode("utf-8")).hexdigest()[:16]

    message_id = make_msgid(domain=_smtp_domain())
    message = _build_message(
        payload,
        from_addr=s.smtp_from,
        to_addr=recipient_email,
        message_id=message_id,
    )

    try:
        # TLS + auth — only if the operator gave a password.
        use_tls = bool(s.smtp_user and s.smtp_password)
        if use_tls:
            smtp = aiosmtplib.SMTP(
                hostname=s.smtp_host,
                port=s.smtp_port,
                use_tls=True,
            )
        else:
            smtp = aiosmtplib.SMTP(hostname=s.smtp_host, port=s.smtp_port)
        async with smtp:
            if s.smtp_user and s.smtp_password:
                await smtp.login(s.smtp_user, s.smtp_password)
            await smtp.send_message(message)
    except Exception as e:  # noqa: BLE001 — RFC 8058: caller retries
        logger.warning(
            "send_digest_email: SMTP send failed",
            extra={
                "digest_id": str(payload.digest_id),
                "recipient_user_id": str(payload.recipient_user_id),
                "recipient_hash": recipient_hash,
                "error_class": type(e).__name__,
            },
        )
        await update_digest_delivery(session, payload.digest_id, status="failed")
        return None

    logger.info(
        "send_digest_email: sent",
        extra={
            "digest_id": str(payload.digest_id),
            "recipient_user_id": str(payload.recipient_user_id),
            "message_id": message_id,
            "recipient_hash": recipient_hash,
        },
    )
    await update_digest_delivery(
        session, payload.digest_id, status="emailed", email_message_id=message_id
    )
    return message_id


__all__ = ["send_digest_email"]
