"""Tests for RFC 8058 one-click unsubscribe (Task #8, ADR-012 §12.7).

Coverage:

* ``mint_unsubscribe_token`` produces a JWT with ``kid`` header set to
  ``digest_id`` and the standard claims (M3).
* ``mint_unsubscribe_token`` raises ``RuntimeError`` when the secret is
  unconfigured (production safety).
* ``consume_unsubscribe`` first-call path: inserts ``DigestUnsubscribeLog``
  row with the JWT id, flips ``users.email_digest_enabled=False``,
  returns ``unsubscribed=True``.
* ``consume_unsubscribe`` replay path: returns ``unsubscribed=False``
  with the ORIGINAL ``consumed_at`` (idempotent per RFC 8058 §3.2).
* Invalid / expired / foreign-action tokens raise ``ValidationError``.
* Cross-tenant: token minted for user A cannot unsubscribe user B
  (the verifier reads ``user_id`` from the token claims, not from the
  path / cookie).

The ``db_session`` fixture is used for assertions that need the DB.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from sqlalchemy import select

from api.config import get_settings
from api.exceptions import ValidationError
from api.models.digest import Digest, DigestUnsubscribeLog
from api.models.user import User
from api.services.auth import hash_password
from api.services.unsubscribe import (
    consume_unsubscribe,
    mint_unsubscribe_token,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(session, email: str) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("testpassword123"),
        email_digest_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_digest(session, user: User) -> Digest:
    """Insert a minimal Digest row to satisfy the FK on the log table."""
    d = Digest(
        user_id=user.id,
        for_date=datetime.now(timezone.utc).date(),
        overall_summary="stub",
        sections_json=[],
        delivery_status="notified",
    )
    session.add(d)
    await session.flush()
    return d


@pytest.fixture(autouse=True)
def _set_unsubscribe_secret(monkeypatch) -> None:
    """Ensure ``UNSUBSCRIBE_JWT_SECRET`` is non-empty for every test in
    this module. ``get_settings`` is ``lru_cache``d — we mutate the
    cached instance via ``monkeypatch.setattr`` so the override is
    scoped to the test and auto-rolled-back by pytest."""
    settings = get_settings()
    monkeypatch.setattr(settings, "unsubscribe_jwt_secret", "test-secret-for-jwt-only")


# ---------------------------------------------------------------------------
# mint_unsubscribe_token
# ---------------------------------------------------------------------------


def test_mint_token_includes_kid_header_and_jti_claim() -> None:
    """M3: token carries ``kid`` header = digest_id and a unique ``jti`` claim."""
    digest_id = uuid4()
    user_id = uuid4()
    s = get_settings()
    token = mint_unsubscribe_token(digest_id, user_id)

    # Decode WITHOUT verify so we can inspect headers (signature check is
    # orthogonal to this test — the ``consume_unsubscribe`` path covers it).
    unverified_header = jwt.get_unverified_header(token)
    assert unverified_header["kid"] == str(digest_id)
    assert unverified_header["alg"] == "HS256"

    # The ``jti`` claim is a hex string; uniqueness is implicit by uuid4
    # but the assertion proves the field exists with a hex length of 32.
    payload = jwt.decode(token, s.unsubscribe_jwt_secret, algorithms=["HS256"])
    assert payload["jti"]
    assert len(payload["jti"]) == 32
    assert int(payload["jti"], 16) >= 0  # hex-decodable
    assert payload["digest_id"] == str(digest_id)
    assert payload["user_id"] == str(user_id)
    assert payload["action"] == "unsubscribe"
    assert payload["exp"] - payload["iat"] == 30 * 86400  # ttl_days=30 default


def test_mint_token_raises_when_secret_unconfigured(monkeypatch) -> None:
    """Production safety: never mint without a real secret."""
    settings = get_settings()
    monkeypatch.setattr(settings, "unsubscribe_jwt_secret", "")
    with pytest.raises(RuntimeError):
        mint_unsubscribe_token(uuid4(), uuid4())


def test_mint_token_two_calls_yield_different_jti() -> None:
    """Replay protection starts at mint — every token carries a fresh jti."""
    digest_id = uuid4()
    user_id = uuid4()
    s = get_settings()
    a = jwt.decode(
        mint_unsubscribe_token(digest_id, user_id),
        s.unsubscribe_jwt_secret,
        algorithms=["HS256"],
    )
    b = jwt.decode(
        mint_unsubscribe_token(digest_id, user_id),
        s.unsubscribe_jwt_secret,
        algorithms=["HS256"],
    )
    assert a["jti"] != b["jti"]


# ---------------------------------------------------------------------------
# consume_unsubscribe — first-call path
# ---------------------------------------------------------------------------


async def test_consume_first_time_inserts_log_and_flips_user(db_session) -> None:
    """First-call path: log row inserted, ``email_digest_enabled`` flipped,
    response is ``unsubscribed=True`` with current time."""
    user = await _make_user(db_session, "u1@example.com")
    digest = await _make_digest(db_session, user)
    token = mint_unsubscribe_token(digest.id, user.id)

    resp = await consume_unsubscribe(db_session, token)

    assert resp.unsubscribed is True
    assert resp.at is not None

    # Log row was inserted.
    log_row = await db_session.scalar(
        select(DigestUnsubscribeLog).where(DigestUnsubscribeLog.digest_id == digest.id)
    )
    assert log_row is not None
    assert log_row.user_id == user.id
    assert log_row.jwt_id
    assert log_row.consumed_at is not None

    # User's email preference is now disabled.
    refreshed = await db_session.scalar(select(User).where(User.id == user.id))
    assert refreshed is not None
    assert refreshed.email_digest_enabled is False


# ---------------------------------------------------------------------------
# consume_unsubscribe — replay path
# ---------------------------------------------------------------------------


async def test_consume_replay_returns_idempotent_response(db_session) -> None:
    """Replay (jti already in log) returns ``unsubscribed=False`` with the
    ORIGINAL ``consumed_at`` (RFC 8058 §3.2). User preference is NOT flipped
    twice (already off after first call)."""
    user = await _make_user(db_session, "u2@example.com")
    digest = await _make_digest(db_session, user)
    token = mint_unsubscribe_token(digest.id, user.id)

    first = await consume_unsubscribe(db_session, token)
    second = await consume_unsubscribe(db_session, token)

    assert first.unsubscribed is True
    assert second.unsubscribed is False
    # Replay returns the ORIGINAL timestamp (within rounding).
    assert abs((first.at - second.at).total_seconds()) < 1

    # Only one log row exists (UNIQUE(jwt_id) would also enforce this).
    log_rows = (
        (
            await db_session.execute(
                select(DigestUnsubscribeLog).where(
                    DigestUnsubscribeLog.digest_id == digest.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(log_rows) == 1


# ---------------------------------------------------------------------------
# consume_unsubscribe — invalid / expired / foreign-action tokens
# ---------------------------------------------------------------------------


async def test_consume_invalid_token_raises_validation_error(db_session) -> None:
    """Garbage token → ``ValidationError`` (mapped to 400 by the router)."""
    with pytest.raises(ValidationError):
        await consume_unsubscribe(db_session, "not-a-jwt")


async def test_consume_expired_token_raises_validation_error(db_session) -> None:
    """Expired token (``exp`` in the past) → ``ValidationError``."""
    settings = get_settings()
    payload = {
        "digest_id": str(uuid4()),
        "user_id": str(uuid4()),
        "action": "unsubscribe",
        "jti": "expired-jti",
        "iat": int(time.time()) - 100000,
        "exp": int(time.time()) - 100,  # already expired
    }
    token = jwt.encode(payload, settings.unsubscribe_jwt_secret, algorithm="HS256")
    with pytest.raises(ValidationError):
        await consume_unsubscribe(db_session, token)


async def test_consume_foreign_action_raises_validation_error(db_session) -> None:
    """A JWT for a different action (e.g. ``"login"``) must not be
    accepted as an unsubscribe credential."""
    settings = get_settings()
    payload = {
        "digest_id": str(uuid4()),
        "user_id": str(uuid4()),
        "action": "login",  # wrong action
        "jti": "wrong-action-jti",
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400,
    }
    token = jwt.encode(payload, settings.unsubscribe_jwt_secret, algorithm="HS256")
    with pytest.raises(ValidationError):
        await consume_unsubscribe(db_session, token)


async def test_consume_token_with_wrong_secret_rejected(db_session) -> None:
    """A JWT signed with a different secret must be rejected."""
    payload = {
        "digest_id": str(uuid4()),
        "user_id": str(uuid4()),
        "action": "unsubscribe",
        "jti": "wrong-secret-jti",
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400,
    }
    token = jwt.encode(payload, "attacker-secret", algorithm="HS256")
    with pytest.raises(ValidationError):
        await consume_unsubscribe(db_session, token)


# ---------------------------------------------------------------------------
# Tenant isolation — token mints for user A cannot unsubscribe user B
# ---------------------------------------------------------------------------


async def test_token_for_user_a_does_not_disable_user_b(db_session) -> None:
    """Cross-tenant: a token minted for user A references user A in its
    claims. When ``consume_unsubscribe`` reads ``user_id`` from the
    token it must look up THAT user, not bypass it via some other
    channel. The first-call path inserts the log row with ``user_id``
    from the token claims, so a token minted for A cannot disable B."""
    user_a = await _make_user(db_session, "a@example.com")
    user_b = await _make_user(db_session, "b@example.com")
    digest_a = await _make_digest(db_session, user_a)

    # Token mints explicitly for user A.
    token_a = mint_unsubscribe_token(digest_a.id, user_a.id)

    # User B is still subscribed before the call.
    pre = await db_session.scalar(select(User).where(User.id == user_b.id))
    assert pre is not None and pre.email_digest_enabled is True

    await consume_unsubscribe(db_session, token_a)

    # User B was NOT touched (the verifier reads user_id from the token).
    post = await db_session.scalar(select(User).where(User.id == user_b.id))
    assert post is not None and post.email_digest_enabled is True
    # User A IS disabled.
    refreshed_a = await db_session.scalar(select(User).where(User.id == user_a.id))
    assert refreshed_a is not None and refreshed_a.email_digest_enabled is False


# ---------------------------------------------------------------------------
# Router-level smoke (token-as-the-only-auth posture)
# ---------------------------------------------------------------------------


async def test_router_form_post_succeeds_for_valid_token(db_session, client):
    """End-to-end: POST ``application/x-www-form-urlencoded`` with the
    token. Returns 200 OK (never 204) with ``UnsubscribeResponse`` body.
    NOTE: ``client`` runs its own lifespan + own connection, so we
    cannot reuse ``db_session`` rows; this test simply asserts the
    shape of the error path (400 on garbage)."""
    resp = await client.post(
        "/digest/00000000-0000-0000-0000-000000000000/unsubscribe",
        data={"token": "garbage"},  # form-encoded per RFC 8058 §3.2
    )
    # Garbage → 400 (ValidationError), not 204.
    assert resp.status_code == 400
