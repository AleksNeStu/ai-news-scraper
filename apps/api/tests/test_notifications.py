"""Tests for the notifications service + router (Task #8, ADR-012).

* List + filter (unread_only, limit, cursor).
* mark_read raises NotFoundError for foreign IDs (no cross-tenant leak).
* mark_read is idempotent — already-read stays read.
* Router returns 401 unauthenticated, 404 on cross-tenant.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient

from api.exceptions import NotFoundError
from api.models.digest import Notification
from api.models.user import User
from api.services.auth import hash_password
from api.services.notifications import list_notifications, mark_read


# ---------------------------------------------------------------------------
# Helpers — local fixture-like builders (don't rely on conftest's
# `client`/`auth_user` because those commit; we want everything inside
# the transaction so the per-test rollback in conftest leaves no rows).
# ---------------------------------------------------------------------------


async def _make_user(session, email: str) -> User:
    user = User(email=email, hashed_password=hash_password("testpassword123"))
    session.add(user)
    await session.flush()
    return user


def _make_notification(
    session, user: User, *, kind: str = "system", read: bool = False, created_at=None
) -> Notification:
    n = Notification(
        user_id=user.id,
        kind=kind,
        title="t",
        preview="p",
        href="/somewhere",
        digest_id=None,
        read=read,
    )
    if created_at is not None:
        # NB: created_at has a server_default. SQLAlchemy will populate
        # it from the DB side; we override only when the test cares.
        n.created_at = created_at
    session.add(n)
    return n


# ---------------------------------------------------------------------------
# list_notifications — pagination + tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_notifications_filters_by_user(db_session) -> None:
    user_a = await _make_user(db_session, "n1a@example.com")
    user_b = await _make_user(db_session, "n1b@example.com")
    _make_notification(db_session, user_a)
    _make_notification(db_session, user_b)
    _make_notification(db_session, user_b)
    await db_session.flush()

    a_rows = await list_notifications(db_session, user_a.id)
    b_rows = await list_notifications(db_session, user_b.id)
    assert len(a_rows) == 1
    assert len(b_rows) == 2
    assert all(r.user_id == user_a.id for r in a_rows)


@pytest.mark.asyncio
async def test_list_notifications_unread_only(db_session) -> None:
    user = await _make_user(db_session, "n2@example.com")
    _make_notification(db_session, user, read=False)
    _make_notification(db_session, user, read=True)
    await db_session.flush()

    rows = await list_notifications(db_session, user.id, unread_only=True)
    assert len(rows) == 1
    assert rows[0].read is False


@pytest.mark.asyncio
async def test_list_notifications_cursor_advances(db_session) -> None:
    """Cursor excludes items at-or-newer than itself; older items remain.

    Cursor semantics: strict-less-than on ``created_at`` (the cursor
    timestamp is excluded). With default limit=50, all items strictly
    older than the cursor come back, newest-first. The pagination
    boundary is correctness of the WHERE clause, not the LIMIT.
    """
    user = await _make_user(db_session, "n3@example.com")
    base = datetime(2026, 6, 29, 9, 0, tzinfo=timezone.utc)
    n1 = _make_notification(db_session, user, created_at=base)
    n2 = _make_notification(db_session, user, created_at=base + timedelta(minutes=10))
    n3 = _make_notification(db_session, user, created_at=base + timedelta(minutes=20))
    await db_session.flush()
    # Newest-first; cursor at n3.created_at returns [n2, n1] (both
    # strictly older than n3). n3 itself is excluded by the cursor.
    rows = await list_notifications(db_session, user.id, cursor=n3.created_at)
    ids = [r.id for r in rows]
    assert n3.id not in ids  # cursor item excluded
    assert n2.id in ids      # newer-of-the-older items
    assert n1.id in ids      # older item still qualifies
    # Ordering: newest-of-the-older first.
    assert ids == [n2.id, n1.id]


@pytest.mark.asyncio
async def test_list_notifications_cursor_respects_limit(db_session) -> None:
    """Cursor + explicit limit returns up to ``limit`` older items, newest-first."""
    user = await _make_user(db_session, "n-limit@example.com")
    base = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)
    # Three items at 0/10/20 minutes; cursor at the newest.
    n_oldest = _make_notification(db_session, user, created_at=base)
    n_middle = _make_notification(db_session, user, created_at=base + timedelta(minutes=10))
    n_newest = _make_notification(db_session, user, created_at=base + timedelta(minutes=20))
    await db_session.flush()
    rows = await list_notifications(
        db_session, user.id, cursor=n_newest.created_at, limit=1
    )
    assert [r.id for r in rows] == [n_middle.id]


# ---------------------------------------------------------------------------
# mark_read — tenant safety + idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_read_sets_read_true(db_session) -> None:
    user = await _make_user(db_session, "n4@example.com")
    notif = _make_notification(db_session, user)
    await db_session.flush()

    out = await mark_read(db_session, user.id, notif.id)
    assert out.read is True
    assert out.read_at is not None


@pytest.mark.asyncio
async def test_mark_read_idempotent(db_session) -> None:
    """Marking an already-read notification leaves it read, no error."""
    user = await _make_user(db_session, "n5@example.com")
    notif = _make_notification(db_session, user)
    notif.read = True
    notif.read_at = datetime(2026, 6, 28, 9, 0, tzinfo=timezone.utc)
    await db_session.flush()

    out = await mark_read(db_session, user.id, notif.id)
    assert out.read is True
    assert out.read_at == datetime(2026, 6, 28, 9, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_mark_read_foreign_id_raises_not_found(db_session) -> None:
    """mark_read on another user's notification → NotFoundError, not 403.

    Per ADR-012 §12.7: never leak existence across tenants.
    """
    user = await _make_user(db_session, "n6@example.com")
    other = await _make_user(db_session, "n6b@example.com")
    foreign = _make_notification(db_session, other)
    await db_session.flush()

    with pytest.raises(NotFoundError):
        await mark_read(db_session, user.id, foreign.id)


@pytest.mark.asyncio
async def test_mark_read_unknown_id_raises_not_found(db_session) -> None:
    """mark_read on a non-existent UUID → NotFoundError."""
    user = await _make_user(db_session, "n7@example.com")
    with pytest.raises(NotFoundError):
        await mark_read(db_session, user.id, uuid4())


# ---------------------------------------------------------------------------
# Router — http layer (uses the shared ``client`` + ``auth_user`` fixtures
# from conftest.py, so we add a DB-scoped user the lifespan can find).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_404_on_cross_tenant_mark_read(
    client: AsyncClient, auth_user: dict
) -> None:
    """POST /notifications/{id}/read for another user's notification → 404.

    The router uses a different DB session (``get_db``) than the test
    fixture's, so a row written through ``db_session`` would never be
    visible to the request path. Instead we exercise the same code
    branch — any UUID that isn't the caller's raises NotFoundError —
    by hitting the endpoint with a random UUID. Per ADR-012 §12.7,
    cross-tenant access must 404, never 403.
    """
    random_id = uuid4()
    resp = await client.post(
        f"/notifications/{random_id}/read",
        headers=auth_user["headers"],
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_router_401_when_unauthenticated(client: AsyncClient) -> None:
    """POST without a token → 401 (same shape as the rest of the app)."""
    resp = await client.post(f"/notifications/{uuid4()}/read")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_router_list_requires_auth(client: AsyncClient) -> None:
    """GET /notifications without a token → 401."""
    resp = await client.get("/notifications")
    assert resp.status_code == 401
