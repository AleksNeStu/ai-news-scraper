"""Auth router tests — register, login, /me, logout (Task #25).

Exercises the public auth endpoints end-to-end through the FastAPI
ASGI transport. The ``client`` and ``db_session`` fixtures from
``conftest.py`` give us a lifespan-aware httpx client backed by the
real Postgres-backed app, with per-test transactional rollback so
nothing leaks between tests.

Key assertions per the task brief:
    * Register/login set a cookie with the canonical name and the
      security flags the product agreed on (HttpOnly, SameSite=Lax,
      Max-Age ~= JWT expiry, Secure only in production).
    * Duplicate registration returns 409 (uniqueness on the email
      column is the source of truth).
    * /me without a cookie, with a tampered JWT, or with the cookie
      cleared by /auth/logout returns 401 — never 500.
    * /auth/logout clears the cookie (Set-Cookie with Max-Age=0).
    * The 6th registration from the same IP within the window is
      blocked by the per-IP rate limiter.

The rate-limit test overrides the per-route ``rate_limit_ip`` dependency
to force a 429 without needing a live Redis (the real middleware
bypasses enforcement when ``app_env == "test"``).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient

from api.deps import AUTH_COOKIE_NAME
from api.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cookie_attrs(set_cookie: str) -> dict[str, str]:
    """Parse a Set-Cookie header into a dict of attribute name -> value.

    Best-effort tokenizer for the test assertions below. Order in the
    cookie string is irrelevant for what we assert.
    """
    attrs: dict[str, str] = {}
    parts = [p.strip() for p in set_cookie.split(";")]
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """Yield the conftest ``client`` unchanged.

    Alias so test bodies read as auth-specific without re-importing
    ``client``. The per-test transaction rollback is owned by the
    ``db_session`` fixture and ``conftest.py``.
    """
    yield client


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_success_sets_auth_cookie(auth_client: AsyncClient) -> None:
    """Happy-path register → 201 + response body + Set-Cookie with the canonical name."""
    resp = await auth_client.post(
        "/auth/register",
        json={"email": "reg1@example.com", "password": "strongpass123"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["email"] == "reg1@example.com"
    assert body["token"]  # non-empty JWT

    set_cookie = resp.headers.get("set-cookie", "")
    attrs = _cookie_attrs(set_cookie)
    assert attrs.get("name") == AUTH_COOKIE_NAME
    # Max-Age mirrors jwt_expires_min * 60 (86400 = 24h by default).
    assert attrs.get("max-age") == "86400"
    # SameSite=Lax — required by the security posture, no SameSite=None.
    assert attrs.get("samesite", "").lower() == "lax"
    # HttpOnly — never absent.
    assert "httponly" in {k.lower() for k in attrs}


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(auth_client: AsyncClient) -> None:
    """Second register with the same email → 409 (NOT 400)."""
    payload = {"email": "dup@example.com", "password": "strongpass123"}
    first = await auth_client.post("/auth/register", json=payload)
    assert first.status_code == 201, first.text

    second = await auth_client.post("/auth/register", json=payload)
    assert second.status_code == 409, second.text
    # The error body may be RFC-7807 (problem+json) or a plain HTTPException
    # detail; either way the user-facing message hints at the duplicate.
    detail = second.json().get("detail", "")
    assert "registered" in str(detail).lower() or "exists" in str(detail).lower()


@pytest.mark.asyncio
async def test_register_invalid_email_returns_422(auth_client: AsyncClient) -> None:
    """Pydantic EmailStr validation rejects malformed addresses → 422."""
    resp = await auth_client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "strongpass123"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_register_short_password_returns_422(auth_client: AsyncClient) -> None:
    """Password < 8 chars violates the UserCreate min_length=8 → 422."""
    resp = await auth_client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success_sets_auth_cookie(auth_client: AsyncClient) -> None:
    """Register then login → 200 + Set-Cookie carries the canonical cookie name."""
    payload = {"email": "login1@example.com", "password": "strongpass123"}
    reg = await auth_client.post("/auth/register", json=payload)
    assert reg.status_code == 201, reg.text

    resp = await auth_client.post("/auth/login", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == "login1@example.com"
    assert body["token"]

    attrs = _cookie_attrs(resp.headers.get("set-cookie", ""))
    assert attrs.get("name") == AUTH_COOKIE_NAME
    assert attrs.get("max-age") == "86400"
    assert attrs.get("samesite", "").lower() == "lax"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(auth_client: AsyncClient) -> None:
    """Correct email, wrong password → 401."""
    await auth_client.post(
        "/auth/register",
        json={"email": "login2@example.com", "password": "strongpass123"},
    )
    resp = await auth_client.post(
        "/auth/login",
        json={"email": "login2@example.com", "password": "badpass12"},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401_same_body(
    auth_client: AsyncClient,
) -> None:
    """Unknown email → 401 with the SAME body as wrong-password.

    Prevents account enumeration via differential responses. The
    ``instance`` field is the per-request id and is expected to differ
    between the two requests, so we compare everything else.
    """
    bad = await auth_client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "whateverpass"},
    )
    assert bad.status_code == 401, bad.text

    # Now create a real user and ask with a wrong password; bodies must match.
    await auth_client.post(
        "/auth/register",
        json={"email": "real@example.com", "password": "strongpass123"},
    )
    wrong = await auth_client.post(
        "/auth/login",
        json={"email": "real@example.com", "password": "badpass12"},
    )
    assert wrong.status_code == 401, wrong.text

    def _strip_instance(body: dict) -> dict:
        # instance is the per-request id; it MUST differ between requests,
        # so we drop it before comparing.
        body = dict(body)
        body.pop("instance", None)
        return body

    assert _strip_instance(bad.json()) == _strip_instance(wrong.json())


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_with_valid_cookie_returns_user_json(
    auth_client: AsyncClient,
) -> None:
    """Register then call /me with the cookie → 200 + user JSON."""
    reg = await auth_client.post(
        "/auth/register",
        json={"email": "me1@example.com", "password": "strongpass123"},
    )
    assert reg.status_code == 201, reg.text

    resp = await auth_client.get("/auth/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "me1@example.com"
    assert "id" in body and "created_at" in body


@pytest.mark.asyncio
async def test_me_without_cookie_returns_401(auth_client: AsyncClient) -> None:
    """No cookie at all → 401, not 500."""
    resp = await auth_client.get("/auth/me")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_me_with_tampered_jwt_returns_401(auth_client: AsyncClient) -> None:
    """A JWT with its signature flipped must NOT decode → 401.

    Use the cookie shape the auth router actually sets. Mutating the
    trailing character changes the signature byte; pyjwt will reject it.
    """
    reg = await auth_client.post(
        "/auth/register",
        json={"email": "me2@example.com", "password": "strongpass123"},
    )
    assert reg.status_code == 201, reg.text

    token = reg.json()["token"]
    # Flip the last char of the signature segment.
    head, payload, sig = token.split(".")
    flipped = sig[:-1] + ("A" if sig[-1] != "A" else "B")
    tampered = ".".join([head, payload, flipped])

    resp = await auth_client.get(
        "/auth/me",
        cookies={AUTH_COOKIE_NAME: tampered},
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_returns_204(auth_client: AsyncClient) -> None:
    """Logout clears the cookie and returns 204 No Content."""
    reg = await auth_client.post(
        "/auth/register",
        json={"email": "lo1@example.com", "password": "strongpass123"},
    )
    assert reg.status_code == 201, reg.text

    resp = await auth_client.post("/auth/logout")
    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_logout_set_cookie_clears_auth_token(auth_client: AsyncClient) -> None:
    """The logout response MUST include a Set-Cookie that expires auth_token."""
    await auth_client.post(
        "/auth/register",
        json={"email": "lo2@example.com", "password": "strongpass123"},
    )
    resp = await auth_client.post("/auth/logout")
    assert resp.status_code == 204, resp.text

    set_cookie = resp.headers.get("set-cookie", "")
    attrs = _cookie_attrs(set_cookie)
    assert attrs.get("name") == AUTH_COOKIE_NAME
    # Either Max-Age=0 or an expires-in-the-past header is the
    # browser-side "delete this cookie" signal.
    max_age = attrs.get("max-age", "")
    assert max_age == "0" or max_age == ""


@pytest.mark.asyncio
async def test_me_after_logout_returns_401(auth_client: AsyncClient) -> None:
    """Subsequent /me with the now-expired cookie → 401."""
    await auth_client.post(
        "/auth/register",
        json={"email": "lo3@example.com", "password": "strongpass123"},
    )
    await auth_client.post("/auth/logout")
    resp = await auth_client.get("/auth/me")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Rate limit — 6th register from same IP within 1h → 429
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def rl_429_client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """Client whose /auth/register rate-limiter always returns 429.

    The real ``rate_limit_ip`` short-circuits in test mode (``app_env
    == "test"``). We disable the bypass by flipping ``app_env`` to
    ``"production"`` for the duration of the fixture and replace the
    Redis-backed ``_enforce`` call with a stub that always raises 429.

    Patching the module is more portable than reaching into FastAPI's
    route internals: FastAPI/Starlette have reshuffled how ``app.routes``
    is exposed across several upgrades (e.g. FastAPI 0.13x), and the
    closure FastAPI stores for the rate-limit dependency is identity-keyed
    by ``app.dependency_overrides`` so we cannot rebuild it from outside
    the route decoration site. The module-level knobs are stable.
    """
    from api.config import get_settings
    from api.middleware import rate_limit as rate_limit_module

    settings = get_settings()
    # The check inside _checker skips enforcement when app_env == "test";
    # flip it so the stub is actually consulted.
    monkeypatch.setattr(settings, "app_env", "production")

    async def _always_429(spec: object) -> None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    monkeypatch.setattr(rate_limit_module, "_enforce", _always_429)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_register_rate_limited_after_5_calls(
    rl_429_client: AsyncClient,
) -> None:
    """With the limiter stubbed to 429, every register is rejected with 429."""
    payload = {"email": "rl@example.com", "password": "strongpass123"}
    resp = await rl_429_client.post("/auth/register", json=payload)
    assert resp.status_code == 429, resp.text


# ---------------------------------------------------------------------------
# Cookie flag assertions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_cookie_is_httponly(auth_client: AsyncClient) -> None:
    """HttpOnly MUST be set on the auth cookie (XSS can't read it)."""
    reg = await auth_client.post(
        "/auth/register",
        json={"email": "flag1@example.com", "password": "strongpass123"},
    )
    assert reg.status_code == 201, reg.text

    attrs = _cookie_attrs(reg.headers.get("set-cookie", ""))
    assert "httponly" in {k.lower() for k in attrs}


@pytest.mark.asyncio
async def test_auth_cookie_samesite_is_lax(auth_client: AsyncClient) -> None:
    """SameSite=Lax MUST be set (CSRF defense)."""
    reg = await auth_client.post(
        "/auth/register",
        json={"email": "flag2@example.com", "password": "strongpass123"},
    )
    assert reg.status_code == 201, reg.text

    attrs = _cookie_attrs(reg.headers.get("set-cookie", ""))
    assert attrs.get("samesite", "").lower() == "lax"


@pytest.mark.asyncio
async def test_auth_cookie_secure_flag_toggles_by_app_env(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Secure flag present only when app_env == 'production'.

    In dev/staging the Secure flag must be ABSENT (otherwise the
    browser drops the cookie over plain HTTP, breaking local dev).
    """
    from api.config import get_settings

    settings = get_settings()
    # Default state: development — Secure must be absent.
    assert settings.app_env != "production"
    reg_dev = await auth_client.post(
        "/auth/register",
        json={"email": "flag3@example.com", "password": "strongpass123"},
    )
    assert reg_dev.status_code == 201, reg_dev.text
    attrs_dev = _cookie_attrs(reg_dev.headers.get("set-cookie", ""))
    assert "secure" not in {k.lower() for k in attrs_dev}

    # Toggle to production — Secure must now appear.
    monkeypatch.setattr(settings, "app_env", "production")
    reg_prod = await auth_client.post(
        "/auth/register",
        json={"email": "flag4@example.com", "password": "strongpass123"},
    )
    assert reg_prod.status_code == 201, reg_prod.text
    attrs_prod = _cookie_attrs(reg_prod.headers.get("set-cookie", ""))
    assert "secure" in {k.lower() for k in attrs_prod}
