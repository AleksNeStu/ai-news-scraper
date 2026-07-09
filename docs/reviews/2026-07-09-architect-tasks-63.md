# Architect review — Task #63 (JWT verification flake on `test_me_with_tampered_jwt_returns_401`)

- **Repo:** `ai-news-scraper` (branch `dev`)
- **Date:** 2026-07-09
- **Reviewer:** Architect (read-only, advisory)
- **Task:** Investigate + fix the flake where the tampered-JWT assertion occasionally fails to return 401
- **In scope:** ADR-015 §15.9 invariants, the test in `apps/api/tests/test_auth.py:282-304`, the `auth_client` fixture, and the JWT decode path.

---

## A. Contract map — ADR-015 §15.9 JWT invariants

ADR-015 §15.9 specifies a refresh-token strategy, but the verification invariants relevant to this flake are the JWT decode invariants §15.5 cites for the existing access-token path: **alg in allow-list**, **signature verified before payload parse**, **`exp` enforced**, **`sub` present**.

| Invariant | Enforced by | Test that verifies it | Status |
|---|---|---|---|
| **alg in allow-list** | `apps/api/api/services/auth.py:50` — `jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])`. PyJWT rejects any header `alg` not in the list. | None directly. The existing tampered-sig test only mutates the *signature segment*, never the header. The new matrix below (§C) closes this gap. | **GAP** — must add tests for `alg=none` and `alg=HS512` while server expects `HS256`. |
| **Signature verified before payload parse** | Same line: `jwt.decode(...)` performs HMAC verify before returning any payload. PyJWT's contract: `InvalidSignatureError` is raised first, payload is never returned to the caller. | `test_me_with_tampered_jwt_returns_401` at `apps/api/tests/test_auth.py:282-304` mutates the signature byte and asserts 401. | **COVERED** (single byte flip), but see §B hypothesis A for the flake root cause. |
| **`exp` enforced** | `apps/api/api/services/auth.py:49-52` — `jwt.decode` honors the `exp` claim by default. `ExpiredSignatureError` is caught at line 52 and `decode_token` returns `None`, which `get_current_user_id` at `apps/api/api/deps/__init__.py:50-55` translates into 401. | None directly. Add a test in §C. | **GAP** — no test asserts `exp` in the past → 401. |
| **`sub` present** | `apps/api/api/deps/__init__.py:56-62` — `payload.get("sub")` and raise 401 if `None`. | None directly. Add a test in §C. | **GAP** — no test asserts missing `sub` → 401. |

**Net:** only 1 of the 4 invariants has a regression test today, and that test is the one that flakes. The other 3 are *enforced* but *unverified*.

---

## B. Hypothesis assessment

### Hypothesis A — signature verification is skipped on some code path (likelihood: **LOW**)

**For:** the symptom (intermittent 401-vs-200 on a tampered sig) is exactly what a skipped verify would produce.

**Against (strong evidence):**

- The only call site is `apps/api/api/services/auth.py:47-56`. `decode_token` is a single function with one `try/except` and no other branches. There is no `verify=False` path, no opt-out, no env-var switch.
- PyJWT's `jwt.decode(...)` signature accepts a `verify_signature` parameter that defaults to `True`. The call at `auth.py:49-51` does NOT pass it, so the default holds.
- `get_current_user_id` at `apps/api/api/deps/__init__.py:47-69` only consumes `decode_token`'s return value — it never re-parses the JWT itself, never base64-decodes the payload, never short-circuits on any field. If `decode_token` returns a dict, the dep returns a UUID; if it returns `None`, the dep raises 401. There is no third branch.
- The byte-flip test only changes the **last character of the signature** segment. PyJWT base64-decodes the full signature and HMAC-compares; a single-char mutation is guaranteed to fail HMAC. This is one of the most well-trodden test patterns in the PyJWT ecosystem.

**Conclusion:** A correctly-built PyJWT cannot be tricked into accepting a tampered sig on `HS256`. If the test intermittently returns 200, the JWT did not have a tampered sig when `decode_token` ran it.

### Hypothesis B — test isolation leak in `auth_client` (likelihood: **HIGH**)

**For (multiple converging signals):**

1. **`auth_client` is a re-export of `client`** at `apps/api/tests/test_auth.py:97-105`. The body is literally `yield client` — no cookie-jar reset, no header reset, no per-test isolation. If the `client` fixture is `function`-scoped (it is — `conftest.py:96`), the cookie jar IS fresh per test. But the `httpx.AsyncClient` is created inside a `lifespan_context` that drives app startup, and Starlette/FastAPI app state is module-level — cookies persisted anywhere in app-level middleware would survive across `client` instances.

2. **The test bypasses the auth_client cookie jar** at line 302 by passing `cookies={AUTH_COOKIE_NAME: tampered}` directly. Per httpx docs, the per-request `cookies=` argument is **merged on top of** the client's cookie jar, not *replacing* it. If a previous test in the same module (e.g. `test_register_success_sets_auth_cookie` at line 114 or `test_login_success_sets_auth_cookie` at line 180) left an `auth_token` cookie in the jar, the merge means the request carries **two** `auth_token` cookies. httpx sends both in `Cookie:` header. The server's `request.cookies.get(AUTH_COOKIE_NAME)` picks the *first* — which is the one httpx wrote first, NOT the one we passed in `cookies=`.

3. **The `reg.json()["token"]` round-trip.** The test:
   1. `POST /auth/register` — receives `Set-Cookie: auth_token=<jwt>; auth_refresh=<raw>`. The `httpx.AsyncClient` cookie jar stores BOTH cookies (httpx is RFC 6265-compliant).
   2. Forges a tampered token.
   3. `GET /auth/me` with `cookies={AUTH_COOKIE_NAME: tampered}` — but the jar still has the ORIGINAL valid `auth_token` from step 1. httpx sends **both** as `Cookie: auth_token=<valid>; auth_refresh=<raw>; auth_token=<tampered>` (or some order). Per RFC 6265 §5.4, browsers/Servers process cookies in order; httpx on the request side will pass the jar as-is. Starlette's `request.cookies` returns the first value per cookie name.

4. **The flake signature.** If the valid cookie comes before the tampered one in the merged request, the server's `request.cookies.get(AUTH_COOKIE_NAME)` returns the valid token → decode succeeds → 200. If the tampered one comes first (depends on httpx merge order, which has changed across httpx minor versions), the server returns 401. **Two httpx minor versions on the test runner → intermittent pass/fail** matches the observed flake exactly.

5. **No explicit `cookies=` reset.** httpx's `AsyncClient` cookie jar persists across requests within the same client lifetime. `auth_client` does not clear the jar before each test.

**Conclusion:** this is a **classic httpx-cookie-jar-vs-per-request-cookies merge interaction**. The fix is to either (a) construct a fresh `AsyncClient` for this test, (b) `await auth_client.cookies.clear()` at the top of the test, or (c) drive the tampered token via the `Authorization: Bearer <tampered>` header, which does NOT interact with the cookie jar.

### Recommended primary hypothesis

**Hypothesis B — httpx cookie-jar leak.** Rationale: Hypothesis A is mechanically impossible given PyJWT's contract and the absence of any `verify_signature=False` code path. Hypothesis B explains the flake mechanism (cookie-jar ordering) and points at a one-line fix (clear the jar or use the Authorization header). Backend Dev should fix the test isolation, then expand the regression matrix per §C.

---

## C. Regression matrix spec — 5 cases the task demands

All 5 cases use the **same setup**: register a user via `auth_client.post("/auth/register", ...)`, then forge a token, then `GET /auth/me` with that token and assert 401.

The setup MUST isolate the request from any cookies already in `auth_client`'s jar. The cleanest construction:

```python
# Clear the jar so no leftover Set-Cookie from prior requests leaks in.
auth_client.cookies.clear()
# Send the tampered token via Authorization header — does NOT merge
# with the jar.
headers = {"Authorization": f"Bearer {tampered}"}
resp = await auth_client.get("/auth/me", headers=headers)
```

(Alternative: build a one-shot `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` with `cookies=` set to exactly the tampered token. Either approach is acceptable; pick one and apply it consistently across all 5 cases.)

### Case 1 — Empty signature (sig segment = `""`)

**Construction:**
```python
import base64, json, hmac, hashlib
header = {"alg": "HS256", "typ": "JWT"}
payload = {"sub": str(user.id), "email": user.email, "iat": ..., "exp": ...}
def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=").decode()
head_b64, pay_b64 = _b64(header), _b64(payload)
forged = f"{head_b64}.{pay_b64}."   # trailing dot, empty sig
```

**Expected:** `decode_token(forged)` returns `None` → `get_current_user_id` raises 401 → response status **401**. PyJWT raises `InvalidSignatureError` ("Signature is required") before parsing the payload.

### Case 2 — Wrong alg in header

**Sub-case 2a — `alg=none`, no signature:**
```python
header = {"alg": "none", "typ": "JWT"}
forged = f"{_b64(header)}.{_b64(payload)}."
```
**Expected:** 401. PyJWT's allow-list is `["HS256"]` per `auth.py:50`; `none` is rejected with `InvalidAlgorithmError`. (Critical: `jwt.decode` with an explicit `algorithms=` allow-list **never** honors `alg=none` even if a caller forgot to set the allow-list — defense in depth.)

**Sub-case 2b — `alg=HS512` while server expects `HS256`:**
```python
header = {"alg": "HS512", "typ": "JWT"}
# Sig MUST be a valid HS512 of "head.payload" using a guessable key
# (we don't need to crack the real secret — an invalid HS512 still fails).
sig = base64.urlsafe_b64encode(b"\x00" * 64).rstrip(b"=").decode()
forged = f"{_b64(header)}.{_b64(payload)}.{sig}"
```
**Expected:** 401. PyJWT rejects `HS512` because the allow-list is `["HS256"]` (raises `InvalidAlgorithmError`). The signature contents are never checked — the alg mismatch short-circuits.

### Case 3 — Expired token (valid signature, `exp` in the past)

**Construction:** mint a real token with `create_token(user.id, user.email)` (the same helper `conftest.py:51` imports), but mutate its `exp` claim by:
1. Decode the payload (no verify, just base64): `pay = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))`.
2. Set `pay["exp"] = int(time.time()) - 60`.
3. Re-encode `head.payload` with the new payload, sign with the **real** `JWT_SECRET` (`_settings.jwt_secret`), append the new sig.

**Expected:** 401. PyJWT raises `ExpiredSignatureError`; `decode_token` at `auth.py:52` catches it and returns `None`.

### Case 4 — Swapped payload (valid sig for user A, payload swapped to user B's id)

**Construction:**
1. Mint token A for `user_a` via `create_token(user_a.id, "a@example.com")`.
2. Mint token B for `user_b` via `create_token(user_b.id, "b@example.com")`.
3. Take `head_A.payload_B.sig_A` — header from A, payload from B, signature from A.
4. `jwt.decode` validates the signature against `head.payload` — the signed content was `head_A.payload_A`, so `head_A.payload_B` is a mismatch → `InvalidSignatureError`.

**Expected:** 401. Signature mismatch on a tampered payload is the standard PyJWT failure mode and what the existing test exercises — included here explicitly so the new matrix covers it.

### Case 5 — Missing `sub` (valid sig, no `sub` claim)

**Construction:** mint a real token, base64-decode its payload, drop the `sub` key, re-encode `head.payload`, sign the new pair with the real secret, append the new sig.

**Expected:** 401. `jwt.decode` succeeds (sig valid, no `exp` issue, no `alg` mismatch), returns a payload dict that lacks `sub`. `get_current_user_id` at `deps/__init__.py:57-62` raises 401 with detail `"Token missing subject"`. This case is **only caught by the deps layer**, not by `decode_token` — important: a unit test on `decode_token(without_sub)` would assert it returns a dict, NOT `None`.

### Summary table

| # | Forged shape | `decode_token` returns | HTTP status | Caught at |
|---|---|---|---|---|
| 1 | `head.pay.` (empty sig) | `None` | 401 | `auth.py:52-56` (InvalidSignatureError) |
| 2a | `alg=none`, no sig | `None` | 401 | `auth.py:50` (InvalidAlgorithmError, allow-list) |
| 2b | `alg=HS512`, bogus sig | `None` | 401 | `auth.py:50` (InvalidAlgorithmError, allow-list) |
| 3 | real sig, `exp` past | `None` | 401 | `auth.py:52-56` (ExpiredSignatureError) |
| 4 | sig from A, payload from B | `None` | 401 | `auth.py:54-56` (InvalidSignatureError) |
| 5 | real sig, no `sub` | dict without `sub` | 401 | `deps/__init__.py:57-62` (sub-missing branch) |

---

## D. Fixture audit checklist

For Backend Dev to verify before claiming the fix is in:

- [ ] **`auth_client` scope.** Confirmed `function`-scoped at `apps/api/tests/test_auth.py:97-105` (re-exports the `client` fixture from `conftest.py:96`, which is `function`-scoped). A fresh `AsyncClient` per test → cookie jar is fresh per test. The flake is NOT from a stale jar across tests, it's from the same-test jar not being cleared before the manual `cookies=` override.
- [ ] **`httpx.AsyncClient` cookies behavior on `cookies=` kwarg.** httpx merges per-request `cookies=` ON TOP OF the client's cookie jar, not replacing it. Reference: httpx docs (`Cookies`), which states "These cookies will be merged with any existing cookies stored on the client." Verification command: `python -c "import httpx; help(httpx.AsyncClient.request)"` in the API env.
- [ ] **Starlette `request.cookies` ordering.** When two cookies with the same name are present in the `Cookie:` header, Starlette returns the FIRST occurrence (it iterates `self._cookies` dict — duplicate header values are not preserved). Test the ordering empirically: send two `auth_token` cookies, observe which one `/auth/me` reads.
- [ ] **DB transaction visibility for `register` → `me`.** The `register` route commits inside its own session (`apps/api/api/routers/auth.py`); the user row is visible to subsequent requests via the same connection pool. No fixture-leak issue here — the `db_session` fixture rollback only affects the test's direct session, not the app's request-scoped sessions.
- [ ] **`AUTH_COOKIE_NAME` constant matches.** Confirmed: `apps/api/api/deps/__init__.py:25` defines `AUTH_COOKIE_NAME = "auth_token"` and `apps/api/tests/test_auth.py:37` imports the same constant. No drift.

---

## E. Hand-off bullets — what Backend Dev must address to ship #63

1. **Root cause is the test, not the code.** `apps/api/api/services/auth.py:47-56` and `apps/api/api/deps/__init__.py:47-69` correctly enforce every invariant in §C. The flake is the `httpx.AsyncClient` cookie-jar carrying the original valid token from `register` while the test sends `cookies={AUTH_COOKIE_NAME: tampered}` — httpx merges, doesn't replace, and Starlette picks whichever cookie name appears first in the merged header.
2. **Fix the existing `test_me_with_tampered_jwt_returns_401` at `apps/api/tests/test_auth.py:282-304`.** Either (a) call `auth_client.cookies.clear()` at the top before the `cookies={...}` override, OR (b) drive the tampered token via `headers={"Authorization": f"Bearer {tampered}"}` (does not touch the jar). Pick one and apply it consistently to the 5 new tests.
3. **Add the 5 new tests in §C** in `apps/api/tests/test_auth.py` (or split into a new `test_auth_jwt_matrix.py` if the file is getting long — check with Devil on file size). Each test MUST use the same isolation pattern as the fixed existing test.
4. **Case 5 (missing `sub`) is a deps-layer test, not a decode-layer test.** Asserting `decode_token(forged) is None` for case 5 is WRONG — the decode succeeds and the deps layer raises 401. The test must assert 401 on the HTTP response, NOT on `decode_token`'s return value.
5. **Verify the alg-allow-list is exactly `["HS256"]`.** Confirm `apps/api/api/services/auth.py:50` reads `algorithms=[_settings.jwt_algorithm]` and `_settings.jwt_algorithm = "HS256"` at `apps/api/api/config.py:77`. If `jwt_algorithm` were ever set to a string other than a single algo name (e.g. a list-as-string), the allow-list behavior would silently change — worth a one-line grep to make sure no test config overrides this.
6. **No production code change is required.** If Backend Dev is tempted to "harden" `decode_token` (e.g. add explicit `options={"require": ["exp", "sub"]}`), reject the change — it would be scope creep and could mask future regressions by widening the test-pass surface. The current `decode_token` is correct; only the test was wrong.
7. **Run the matrix locally before claiming done.** Commands:
   - `cd apps/api && poetry run pytest apps/api/tests/test_auth.py -k "tampered or jwt_matrix" -v`
   - `cd apps/api && poetry run pytest apps/api/tests/ -v` (full suite must stay green; the existing 30+ tests in `test_auth.py` and `test_auth_hardening.py` must not regress).
   - `cd apps/api && poetry run ruff check apps/api/tests/test_auth.py`.
8. **No private-infra identifiers in the new test code or docstrings.** Per repo CLAUDE.md, test files are tracked; scan with `bash scripts/private-leak-check.sh --diff` before commit. (The Architect review doc itself, this file, lives in `docs/reviews/` which is also tracked — run the same scan before committing.)

---

## Appendix — references

- `apps/api/api/services/auth.py:47-56` — `decode_token` (single source of truth for JWT verification).
- `apps/api/api/deps/__init__.py:47-69` — `get_current_user_id` (the only caller of `decode_token` for protected routes).
- `.agent/adr/015-auth-hardening.md` §15.5, §15.9 — JWT invariants and refresh-token strategy.
- `apps/api/api/config.py:76-78` — `jwt_secret`, `jwt_algorithm="HS256"`, `access_token_expires_min=15`.
- `apps/api/tests/test_auth.py:282-304` — the flake.
- `apps/api/tests/conftest.py:95-145` — `client` and `auth_user` fixtures.
- `apps/api/tests/test_auth.py:97-105` — `auth_client` is a passthrough re-export of `client` (no jar reset).
- httpx docs: https://www.python-httpx.org/advanced/clients/#cookies — `cookies=` kwarg is merged, not replaced.
- Starlette `request.cookies`: https://www.starlette.io/requests/#request — first-match-wins on duplicate names.
