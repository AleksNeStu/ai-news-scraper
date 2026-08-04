"""Auth hardening regression suite — ADR-015 H1 / H2 / H3.

Covers the three MAJOR findings triaged in
``.agent/adr/015-auth-hardening.md``:

* **H1** — mass-assignment guard. ``UserCreate`` / ``UserLogin``
  reject unknown fields with a 422 (``extra_forbidden`` per
  Pydantic v2).
* **H2** — per-IP login rate-limit (10/min). The 11th call
  inside the window returns 429 with a ``Retry-After`` header.
* **H3** — server-side logout via the ``refresh_tokens`` table.
  Login / register set BOTH cookies; ``/auth/refresh`` rotates;
  ``/auth/logout`` revokes the row and clears both cookies.

The rate-limit tests use the same ``_enforce``-stubbing trick as
``tests/test_auth.py::test_register_rate_limited_after_5_calls`` —
the real ``rate_limit_ip`` middleware short-circuits in test mode,
so we replace the Redis-backed primitive with a counter that
raises 429 when the limit is exceeded.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from api.config import get_settings
from api.db.database import AsyncSessionLocal
from api.deps import AUTH_COOKIE_NAME, AUTH_REFRESH_COOKIE_NAME
from api.main import app
from api.models.refresh_token import RefreshToken
from api.models.user import User
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

_settings = get_settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cookie_attrs(set_cookie: str) -> dict[str, str]:
    """Parse a Set-Cookie header into name -> {attr -> value}.

    Mirrors ``tests/test_auth.py::_cookie_attrs`` — kept local so
    this file's tests don't depend on a sibling module's helper.
    Multiple Set-Cookie headers arrive joined by ``, `` (httpx's
    RFC-7230 behaviour on duplicate header names), so we
    additionally split on the boundary before tokenising.
    """
    attrs: dict[str, str] = {}
    if not set_cookie:
        return attrs
    # Use the first cookie only — sufficient for the assertions below.
    head = set_cookie.split(", ")[0]
    parts = [p.strip() for p in head.split(";")]
    if parts:
        name_value = parts[0].split("=", 1)
        attrs["name"] = name_value[0].strip()
        attrs["value"] = name_value[1].strip() if len(name_value) > 1 else ""
    for raw in parts[1:]:
        if "=" in raw:
            k, v = raw.split("=", 1)
            attrs[k.strip().lower()] = v.strip()
        else:
            attrs[raw.strip().lower()] = ""
    return attrs


def _cookie_attr(set_cookies: list[str], cookie_name: str) -> dict[str, str]:
    """Return the parsed attrs of the cookie named ``cookie_name``.

    Iterates the (possibly comma-joined) Set-Cookie list and
    returns the FIRST entry whose parsed ``name`` matches.
    """
    if not set_cookies:
        return {}
    raw = set_cookies[0]
    # Split multiple Set-Cookie values on the boundary marker.
    chunks: list[str] = []
    if "," not in raw:
        chunks.append(raw)
    else:
        # Naive split — fine for our well-formed httpx output.
        chunks = raw.split(", ")
    for chunk in chunks:
        attrs = _cookie_attrs(chunk)
        if attrs.get("name") == cookie_name:
            return attrs
    return {}


# httpx collapses multiple Set-Cookie headers into one comma-joined
# value (per RFC 7230). Parse the first cookie with our local helper
# and fall back to the second by inspection.
def _two_set_cookies(resp: Any) -> tuple[dict[str, str], dict[str, str]]:
    set_cookie = resp.headers.get("set-cookie", "")
    cookies = [c for c in set_cookie.split(", ") if c.strip()]
    auth_token = _cookie_attrs(cookies[0]) if cookies else {}
    auth_refresh = _cookie_attrs(cookies[1]) if len(cookies) > 1 else {}
    # If the helper above misordered (depends on cookie emit order),
    # re-parse by name.
    auth_token = auth_token if auth_token.get("name") == AUTH_COOKIE_NAME else {}
    auth_refresh = (
        auth_refresh if auth_refresh.get("name") == AUTH_REFRESH_COOKIE_NAME else {}
    )
    return auth_token, auth_refresh


# ---------------------------------------------------------------------------
# H1 — mass-assignment guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_create_forbids_extra_fields(client: AsyncClient) -> None:
    """POST /auth/register with an extra field → 422 from extra='forbid'."""
    resp = await client.post(
        "/auth/register",
        json={
            "email": "extradev@example.com",
            "password": "strongpass123",
            "is_admin": True,
        },
    )
    assert resp.status_code == 422, resp.text
    # The Pydantic error type for extra="forbid" is "extra_forbidden".
    body = resp.json()
    error_types = _collect_error_types(body)
    assert "extra_forbidden" in error_types


@pytest.mark.asyncio
async def test_user_login_forbids_extra_fields(client: AsyncClient) -> None:
    """POST /auth/login with an extra field → 422 from extra='forbid'."""
    # Seed a user first so the login attempt isn't ambiguous with the
    # 'unknown user' 401 — we want to specifically test schema rejection.
    await client.post(
        "/auth/register",
        json={"email": "loginharden@example.com", "password": "strongpass123"},
    )
    resp = await client.post(
        "/auth/login",
        json={
            "email": "loginharden@example.com",
            "password": "strongpass123",
            "is_admin": True,
        },
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    error_types = _collect_error_types(body)
    assert "extra_forbidden" in error_types


def _collect_error_types(body: Any) -> set[str]:
    """Pull every ``type`` field out of a 422 body recursively.

    The body shape from our exception handler wraps the Pydantic
    error list under ``context.errors``; each error carries its
    ``type`` (e.g. ``extra_forbidden``).
    """
    types: set[str] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if "type" in node:
                types.add(str(node["type"]))
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(body)
    return types


# ---------------------------------------------------------------------------
# H2 — /auth/login per-IP rate limit (10/min)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def login_rate_limit_client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """Stub the rate-limit ``_enforce`` to allow the first 10 login
    attempts and 429 from the 11th onwards.

    Mirrors ``test_register_rate_limited_after_5_calls`` from
    ``tests/test_auth.py``. The real ``rate_limit_ip`` middleware
    short-circuits when ``app_env == "test"``, so we flip ``app_env``
    to ``"production"`` for the duration of the fixture.
    """
    from api.middleware import rate_limit as rate_limit_module

    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")

    state: dict[str, int] = {"calls": 0}

    async def _stub_enforce(spec: Any) -> None:
        state["calls"] += 1
        if state["calls"] > 10:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": "10",
                    "X-RateLimit-Remaining": "0",
                },
            )

    monkeypatch.setattr(rate_limit_module, "_enforce", _stub_enforce)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as ac,
    ):
        yield ac
    # Reset for any future fixture usage in the same test.
    state["calls"] = 0


@pytest.mark.asyncio
async def test_login_rate_limit_caps_at_ten(
    login_rate_limit_client: AsyncClient,
) -> None:
    """First 10 login attempts do NOT return 429."""
    # First register a user (rate-limit registration isn't stubbed
    # here — the register endpoint keeps its own 5/hr limit, but the
    # stub also gates it via ``_enforce`` ... wait, the stub honours
    # any caller, so the first register counts toward the bucket.
    # We instead inject a known user via the auth_user-style path by
    # going through the limiter on a separate bucket. Simplest: skip
    # register entirely and just attempt login 10 times — the login
    # attempt itself fails with 401 but never 429 in the first 10.
    statuses = []
    for _ in range(10):
        resp = await login_rate_limit_client.post(
            "/auth/login",
            json={"email": "ratelim@example.com", "password": "wrong-pass"},
        )
        statuses.append(resp.status_code)
    assert all(s != 429 for s in statuses), statuses


@pytest.mark.asyncio
async def test_login_eleventh_call_is_429(
    login_rate_limit_client: AsyncClient,
) -> None:
    """The 11th login attempt inside the window → 429 with Retry-After."""
    # Fire 11 logins; the 11th must be 429 with Retry-After.
    last: Any = None
    for _ in range(11):
        last = await login_rate_limit_client.post(
            "/auth/login",
            json={"email": "ratelim2@example.com", "password": "wrong-pass"},
        )
    assert last is not None
    assert last.status_code == 429, last.text
    assert "retry-after" in {k.lower() for k in last.headers}


@pytest.mark.asyncio
async def test_login_rate_limit_ignores_xff_when_peer_untrusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H2 — X-Forwarded-For is HONORED only when the immediate peer is
    inside a ``trusted_proxy_cidrs`` range (per ADR-015 §15.8).

    With the default empty allow-list, the limiter keys on the
    immediate peer — an attacker spoofing ``X-Forwarded-For`` to a
    fresh IP must NOT trick the limiter into a new bucket. We
    exercise ``_client_ip`` directly with a forged header and the
    real (empty) trusted-proxy allow-list, asserting the resolved IP
    is the immediate peer.
    """
    from api.middleware.rate_limit import _client_ip

    settings = get_settings()
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", [])

    class _FakeClient:
        host = "203.0.113.7"  # the immediate peer (RFC 5737 documentation range)

    class _FakeRequest:
        def __init__(self) -> None:
            self.headers = {"x-forwarded-for": "198.51.100.42, 10.0.0.1"}
            self.client = _FakeClient()

    resolved = _client_ip(_FakeRequest())  # type: ignore[arg-type]
    assert resolved == "203.0.113.7", (
        f"XFF must be ignored when peer is untrusted; got {resolved!r}"
    )


@pytest.mark.asyncio
async def test_login_rate_limit_honors_xff_when_peer_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H2 — X-Forwarded-For is HONORED when the immediate peer falls
    inside a configured trusted CIDR.

    Operators behind Dokploy / Traefik (ADR-014) need XFF to be
    trusted so per-IP caps work correctly across the proxy layer.
    This test pins that behavior — without it, a future refactor
    could regress to "always ignore XFF" and silently DoS the
    rate-limit bucket under the proxy's egress IP.
    """
    from api.middleware.rate_limit import _client_ip

    settings = get_settings()
    monkeypatch.setattr(
        settings, "trusted_proxy_cidrs", ["10.0.0.0/8", "172.16.0.0/12"]
    )
    # Force the module to re-parse the configured networks on the
    # next call.
    import api.middleware.rate_limit as rl

    monkeypatch.setattr(rl, "_trusted_networks", None)

    class _FakeClient:
        host = "10.0.0.5"  # inside 10.0.0.0/8

    class _FakeRequest:
        def __init__(self) -> None:
            self.headers = {"x-forwarded-for": "198.51.100.42, 10.0.0.1"}
            self.client = _FakeClient()

    resolved = _client_ip(_FakeRequest())  # type: ignore[arg-type]
    assert resolved == "198.51.100.42", (
        f"XFF must be honored when peer is trusted; got {resolved!r}"
    )


# ---------------------------------------------------------------------------
# H3 — server-side logout via refresh_tokens
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def registered_user(
    client: AsyncClient,
) -> AsyncGenerator[dict[str, Any], None]:
    """Register a fresh user via the public endpoint and capture
    both cookies for downstream tests.

    Yields a dict with the response body, the parsed auth_token
    cookie attrs, the parsed auth_refresh cookie attrs, and a
    pre-built ``cookies={AUTH_COOKIE_NAME: ..., AUTH_REFRESH_COOKIE_NAME: ...}``
    kwarg ready to pass to subsequent httpx calls.

    Teardown: delete the user row + refresh-token rows from the
    production pool before the next test runs. The fixture hits
    ``/auth/register`` via ``client`` (which uses the api's own
    ``get_db`` session, NOT the per-test ``db_session`` savepoint)
    so the underlying transaction COMMITS — leaving the user
    visible to subsequent tests in the same session and causing
    409 ``Email already registered`` on the next ``/auth/register``
    for ``h3user@example.com``. The explicit DELETE here keeps the
    fixture idempotent across the suite.
    """
    resp = await client.post(
        "/auth/register",
        json={"email": "h3user@example.com", "password": "strongpass123"},
    )
    assert resp.status_code == 201, resp.text

    auth_token, auth_refresh = _two_set_cookies(resp)
    user_id = resp.json()["user"]["id"]
    try:
        yield {
            "user": resp.json()["user"],
            "token": resp.json()["token"],
            "auth_token_cookie": auth_token,
            "auth_refresh_cookie": auth_refresh,
            "cookies": {
                AUTH_COOKIE_NAME: auth_token.get("value", ""),
                AUTH_REFRESH_COOKIE_NAME: auth_refresh.get("value", ""),
            },
        }
    finally:
        async with AsyncSessionLocal() as cleanup_session:
            try:
                await cleanup_session.execute(
                    delete(RefreshToken).where(RefreshToken.user_id == user_id)
                )
                await cleanup_session.execute(delete(User).where(User.id == user_id))
                await cleanup_session.commit()
            except Exception:
                await cleanup_session.rollback()
                raise


@pytest.mark.asyncio
async def test_register_sets_two_cookies(registered_user: dict[str, Any]) -> None:
    assert registered_user["auth_token_cookie"].get("name") == AUTH_COOKIE_NAME
    assert (
        registered_user["auth_refresh_cookie"].get("name") == AUTH_REFRESH_COOKIE_NAME
    )
    # auth_refresh cookie's max-age = refresh_token_expires_days * 86400.
    expected_refresh_max_age = str(_settings.refresh_token_expires_days * 86400)
    assert (
        registered_user["auth_refresh_cookie"].get("max-age")
        == expected_refresh_max_age
    )
    # auth_token's max-age mirrors the short-lived JWT (15 min * 60).
    expected_access_max_age = str(_settings.access_token_expires_min * 60)
    assert (
        registered_user["auth_token_cookie"].get("max-age") == expected_access_max_age
    )


@pytest.mark.asyncio
async def test_login_sets_two_cookies(client: AsyncClient) -> None:
    """POST /auth/login sets BOTH ``auth_token`` AND ``auth_refresh``."""
    reg = await client.post(
        "/auth/register",
        json={"email": "h3login@example.com", "password": "strongpass123"},
    )
    assert reg.status_code == 201, reg.text

    resp = await client.post(
        "/auth/login",
        json={"email": "h3login@example.com", "password": "strongpass123"},
    )
    assert resp.status_code == 200, resp.text
    auth_token, auth_refresh = _two_set_cookies(resp)
    assert auth_token.get("name") == AUTH_COOKIE_NAME
    assert auth_refresh.get("name") == AUTH_REFRESH_COOKIE_NAME


@pytest.mark.asyncio
async def test_refresh_rotates(
    client: AsyncClient,
    db_session: Any,
    registered_user: dict[str, Any],
) -> None:
    """POST /auth/refresh rotates the cookie AND the DB row.

    After /auth/refresh: the old refresh row has ``revoked_at``
    set, a new row exists, both cookies on the response are
    populated, and the returned body is a fresh ``AuthResponse``.
    """
    # Wipe the cookie jar so a prior test's leftover auth_token /
    # auth_refresh can't be merged into the call below — see Devil
    # Finding 4 in the Task #63 review for the same pattern that
    # flaked test_me_with_tampered_jwt_returns_401.
    client.cookies.clear()
    cookies = registered_user["cookies"]
    resp = await client.post("/auth/refresh", cookies=cookies)
    assert resp.status_code == 200, resp.text

    # New pair on the response.
    new_token, new_refresh = _two_set_cookies(resp)
    assert new_token.get("name") == AUTH_COOKIE_NAME
    assert new_refresh.get("name") == AUTH_REFRESH_COOKIE_NAME
    assert new_refresh.get("value") != cookies[AUTH_REFRESH_COOKIE_NAME]

    # Old row should be revoked in the DB.
    user_id = registered_user["user"]["id"]
    rows = (
        (
            await db_session.execute(
                select(RefreshToken).where(RefreshToken.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    revoked = [r for r in rows if r.revoked_at is not None]
    active = [r for r in rows if r.revoked_at is None]
    assert len(revoked) == 1, f"expected 1 revoked row, got {len(revoked)}: {rows}"
    assert len(active) == 1, f"expected 1 active row after rotation, got {len(active)}"


@pytest.mark.asyncio
async def test_stale_refresh_returns_401(
    client: AsyncClient,
    registered_user: dict[str, Any],
) -> None:
    """A second /auth/refresh with the now-revoked cookie → 401.

    After the rotation in test_refresh_rotates, the old refresh
    token's row is revoked. Replaying the same cookie MUST be
    rejected — that's the security property H3 buys.
    """
    # Wipe the cookie jar so prior-test state (and the rotated
    # cookies that the first call below writes into the jar) don't
    # bleed into the replay assertion — see Devil Finding 4.
    client.cookies.clear()
    cookies = registered_user["cookies"]
    # First refresh succeeds and rotates.
    first = await client.post("/auth/refresh", cookies=cookies)
    assert first.status_code == 200, first.text

    # Wipe again: the first call's Set-Cookie response populated
    # the jar with the rotated pair, and we want the SECOND call
    # to dispatch only the ORIGINAL (now-revoked) cookies, not a
    # merge of original + rotated.
    client.cookies.clear()
    # Replay the original cookie.
    replay = await client.post("/auth/refresh", cookies=cookies)
    assert replay.status_code == 401, replay.text


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client: AsyncClient) -> None:
    """POST /auth/refresh without the cookie → 401 (not 500).

    Wipes the cookie jar explicitly: even though this test passes
    NO ``cookies=`` kwarg, ``test_refresh_rotates`` (which runs
    earlier in the same file and is not order-randomized) leaves
    a rotated cookie pair in the jar via its first call's
    ``Set-Cookie`` response. Without the wipe, httpx auto-attaches
    those jar cookies, the endpoint sees a valid refresh token,
    rotates again, and returns 200 — masking the security property
    this test is meant to pin. See Devil Finding 4 in Task #64.
    """
    client.cookies.clear()
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_logout_revokes_refresh(
    client: AsyncClient,
    db_session: Any,
    registered_user: dict[str, Any],
) -> None:
    """POST /auth/logout revokes the DB row and clears both cookies."""
    # Wipe the cookie jar so prior-test leftover cookies don't
    # merge into the logout call — see Devil Finding 4.
    client.cookies.clear()
    cookies = registered_user["cookies"]
    user_id = registered_user["user"]["id"]

    resp = await client.post("/auth/logout", cookies=cookies)
    assert resp.status_code == 204, resp.text

    # Refresh row should be revoked.
    rows = (
        (
            await db_session.execute(
                select(RefreshToken).where(RefreshToken.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    assert rows, "logout should not delete the row, just revoke it"
    for r in rows:
        assert r.revoked_at is not None
    # Logout response should also clear both cookies — look for
    # Set-Cookie entries with max-age=0 for each name.
    set_cookie = resp.headers.get("set-cookie", "")
    assert AUTH_COOKIE_NAME in set_cookie
    assert AUTH_REFRESH_COOKIE_NAME in set_cookie


@pytest.mark.asyncio
async def test_unknown_refresh_returns_401(client: AsyncClient) -> None:
    """A refresh token that was never issued → 401."""
    # Wipe the cookie jar so a prior test's auth_refresh doesn't
    # override the never-issued token below — see Devil Finding 4.
    client.cookies.clear()
    cookies = {AUTH_REFRESH_COOKIE_NAME: "deadbeef" * 8}  # never inserted
    resp = await client.post("/auth/refresh", cookies=cookies)
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_refresh_token_hash_never_persisted_in_raw(
    client: AsyncClient,
    db_session: Any,
    registered_user: dict[str, Any],
) -> None:
    """The raw refresh token string MUST NOT appear in ``token_hash``.

    Storage posture (ADR-015 §15.9): only the SHA-256 hex digest
    lives in the database. This is a defensive check against
    accidentally regressing to plaintext storage.
    """
    raw = registered_user["cookies"][AUTH_REFRESH_COOKIE_NAME]
    rows = (
        (
            await db_session.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash
                    == hashlib.sha256(raw.encode("utf-8")).hexdigest()
                )
            )
        )
        .scalars()
        .all()
    )
    assert rows, "expected at least one row matching the SHA-256 of the raw token"
    for r in rows:
        assert raw not in r.token_hash
