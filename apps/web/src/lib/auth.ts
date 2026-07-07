'use server'

import { cookies } from 'next/headers'
import { api, ApiError } from './api'
import { performLogout } from './auth/logout'
import { createTranslator } from 'next-intl'

const COOKIE_NAME = 'auth_token'
const REFRESH_COOKIE_NAME = 'auth_refresh'
const COOKIE_MAX_AGE = 60 * 60 * 24 // 1d mirror of API
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7 // 7d mirror of API

/**
 * Forward the API's ``Set-Cookie`` headers to the user's browser so
 * the refresh cookie (added in ADR-015 §15.9) is actually persisted.
 *
 * The ``api`` wrapper returns only the parsed JSON body — Set-Cookie
 * headers are dropped on the floor if we do not extract them here.
 * Next server actions run on the server, so the cookies forwarded
 * via ``cookies().set`` are written to the response that goes back
 * to the browser. Without this step, H3 is broken on the frontend:
 * the refresh row is never created client-side, logout can't find
 * a row to revoke, and ``/auth/refresh`` always returns 401.
 *
 * The API controls the source-of-truth cookie attributes (HttpOnly,
 * env-gated Secure, SameSite=Lax, path="/"). We mirror those flags
 * verbatim so the browser attributes match — see
 * ``apps/api/api/routers/auth.py::_set_auth_cookies``.
 */
async function forwardAuthCookies(headers: Headers) {
  const jar = await cookies()
  const setCookieValues =
    typeof headers.getSetCookie === 'function'
      ? headers.getSetCookie()
      : parseSetCookieHeader(headers.get('set-cookie'))
  for (const raw of setCookieValues) {
    const parsed = parseSetCookie(raw)
    if (!parsed) continue
    const isProd = process.env.NODE_ENV === 'production'
    if (parsed.name === COOKIE_NAME) {
      jar.set(COOKIE_NAME, parsed.value, {
        httpOnly: true,
        secure: isProd,
        sameSite: 'lax',
        path: '/',
        maxAge: COOKIE_MAX_AGE,
      })
    } else if (parsed.name === REFRESH_COOKIE_NAME) {
      jar.set(REFRESH_COOKIE_NAME, parsed.value, {
        httpOnly: true,
        secure: isProd,
        sameSite: 'lax',
        path: '/',
        maxAge: REFRESH_MAX_AGE,
      })
    }
  }
}

/**
 * Parse a single Set-Cookie header line into ``{name, value}``.
 * Returns ``null`` if the line is empty / malformed. We only need
 * the name + value to forward the cookie; attributes (Path, Expires,
 * Max-Age, HttpOnly, Secure, SameSite) are reapplied on the
 * forwarding ``cookies().set`` call so they match the API's choice.
 */
function parseSetCookie(raw: string): { name: string; value: string } | null {
  if (!raw) return null
  const sep = raw.indexOf('=')
  if (sep <= 0) return null
  const name = raw.slice(0, sep).trim()
  // Value ends at the first ``;`` (cookie-attribute separator).
  const semi = raw.indexOf(';', sep)
  const value = (semi === -1 ? raw.slice(sep + 1) : raw.slice(sep + 1, semi)).trim()
  if (!name) return null
  return { name, value }
}

/** Join multiple Set-Cookie header values; defensive fallback for runtimes
 *  that do not implement the structured ``getSetCookie()`` method. */
function parseSetCookieHeader(header: string | null): string[] {
  if (!header) return []
  return header
    .split(/,(?=[^ ;]+=)/g)
    .map((s) => s.trim())
    .filter(Boolean)
}

/**
 * Action state shape for login.
 *
 * - `ok: true` → server returned 2xx; the action redirect()ed to `/` so the
 *   client never renders this branch.
 * - `ok: false, error: ...` → generic auth failure (401, 5xx, network).
 * - `ok: false, code: 'rate_limited', retryAfter: <seconds>` → server returned
 *   429 (per ADR-015 §15.8); the login page renders a live countdown and
 *   disables submit until `retryAfter` elapses.
 */
export type LoginState = {
  ok: boolean
  error?: string
  code?: 'rate_limited'
  retryAfter?: number
}

/**
 * Build a server-side translator for the active locale (Task #32).
 *
 * Server actions do NOT automatically receive the active locale — next-intl
 * exposes `getLocale()` from `next-intl/server` which we call inside the
 * action and pass through to this helper. We then load the matching
 * `messages/{locale}.json` and wrap `createTranslator` so we can resolve
 * ICU placeholders in the action's error strings (e.g. the 429 cooldown
 * message with the `{seconds, plural, ...}` plural).
 *
 * For an invalid/unknown locale we fall back to `en` rather than throw,
 * so a malformed query never crashes the server action.
 */
async function tFor(locale: string | undefined) {
  const safe = locale && (locale === 'en' || locale === 'ru') ? locale : 'en'
  const messages = (await import(`@/messages/${safe}.json`)).default
  return createTranslator({ locale: safe, messages })
}

export async function loginAction(
  _prev: LoginState,
  formData: FormData,
  locale?: string
): Promise<LoginState> {
  const t = await tFor(locale)
  const email = String(formData.get('email') ?? '')
  const password = String(formData.get('password') ?? '')
  try {
    const { data, headers } = await api.postWithHeaders<{ user: unknown; token: string }>(
      '/auth/login',
      { email, password }
    )
    ;(await cookies()).set(COOKIE_NAME, data.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: COOKIE_MAX_AGE,
    })
    await forwardAuthCookies(headers)
    return { ok: true }
  } catch (e) {
    if (e instanceof ApiError) {
      // 429 — surface Retry-After so the login page can run a countdown and
      // re-enable the submit button when it expires.
      if (e.status === 429) {
        const retryAfter = parseRetryAfter(e.headers)
        return {
          ok: false,
          code: 'rate_limited',
          retryAfter,
          error: t('Auth.Login.error.cooldown', { seconds: retryAfter }),
        }
      }
      return { ok: false, error: e.message }
    }
    return { ok: false, error: t('Auth.Login.error.failed') }
  }
}

/**
 * Action state shape for register.
 *
 * - `ok: true` → server returned 2xx; the action redirected to `/`.
 * - `ok: false, error: ...` → generic failure.
 * - `ok: false, code: 'validation_error', fieldErrors: { field: msg }` → Pydantic
 *   422. `fieldErrors` maps field name → message so the form can render
 *   each rejected field inline. Special-cased: an `extra_forbidden` field
 *   means the client tried to send a key the API does not expect (H1, per
 *   ADR-015 §15.7).
 */
export type RegisterState = {
  ok: boolean
  error?: string
  code?: 'validation_error'
  fieldErrors?: Record<string, string>
}

export async function registerAction(
  _prev: RegisterState,
  formData: FormData,
  locale?: string
): Promise<RegisterState> {
  const t = await tFor(locale)
  const email = String(formData.get('email') ?? '')
  const password = String(formData.get('password') ?? '')
  try {
    const { data, headers } = await api.postWithHeaders<{ user: unknown; token: string }>(
      '/auth/register',
      {
        email,
        password,
      }
    )
    ;(await cookies()).set(COOKIE_NAME, data.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: COOKIE_MAX_AGE,
    })
    await forwardAuthCookies(headers)
    return { ok: true }
  } catch (e) {
    if (e instanceof ApiError) {
      // 422 — Pydantic v2 problem+json shape: `detail` is an array of
      // `{type, loc, msg, input, ...}`. Extract per-field messages so the
      // form can show "is_admin: field not allowed" rather than the raw blob.
      if (e.status === 422) {
        const fieldErrors = parsePydanticFieldErrors(e.message)
        if (fieldErrors) {
          return { ok: false, code: 'validation_error', fieldErrors }
        }
      }
      return { ok: false, error: e.message }
    }
    return { ok: false, error: t('Auth.Register.error.failed') }
  }
}

/**
 * Server-action logout. Calls `/auth/logout` first (which revokes the
 * refresh token server-side per ADR-015 §15.9), then on 2xx clears the
 * cookie and redirects to `/login`. On a server-side 5xx the cookie is
 * left intact and the action returns an error state — the caller (header
 * logout button) surfaces the failure to the user instead of silently
 * swallowing it.
 *
 * Returns ``never`` on the success path because ``performLogout`` calls
 * ``redirect('/login')`` which is a typed ``never`` (per Next's
 * ``navigate``-style helpers). The error path returns a discriminated
 * object the caller can render.
 *
 * i18n (Task #32):
 *   - The error message is resolved via `tFor(locale)` so the inline
 *     error on the logout button reads "Logout failed. Please try again."
 *     in EN and "Не удалось выйти. Попробуйте ещё раз." in RU. The
 *     default fallback in `performLogout` stays English-only because
 *     performLogout does not have access to the locale; the action
 *     wrapper here catches that path and re-localizes before returning.
 */
export async function logoutAction(
  locale?: string
): Promise<never | { ok: false; error: string }> {
  const t = await tFor(locale)
  const result = await performLogout()
  if (result.kind === 'error') {
    // `performLogout` returns a discriminated `code`, not a
    // pre-formatted English message (Devil-4 finding). Map the code
    // to a translation key here so the UI reads in the active locale
    // regardless of whether the failure was a 5xx or a network error.
    if (result.code === 'logout_failed') {
      return { ok: false, error: t('Auth.Logout.failed') }
    }
    // Exhaustiveness guard — if a new code is added later, TS will
    // fail this branch until handled.
    const _exhaustive: never = result
    return { ok: false, error: t('Auth.Logout.failed') }
  }
  // Unreachable — ``performLogout`` either returns an error or
  // calls ``redirect('/login')``, both of which are typed
  // appropriately.
  return { ok: false, error: t('Auth.Logout.failed') }
}

/** Read the Retry-After header (seconds). Defaults to 60 if missing/invalid. */
function parseRetryAfter(headers?: Headers): number {
  if (!headers) return 60
  const raw = headers.get('retry-after')
  if (!raw) return 60
  const seconds = Number.parseInt(raw, 10)
  return Number.isFinite(seconds) && seconds > 0 ? seconds : 60
}

/**
 * Parse a Pydantic v2 422 body into a `{ field: message }` map.
 *
 * Pydantic v2 returns `detail` as an array of objects:
 *   [{type: "extra_forbidden", loc: ["body", "is_admin"], msg: "Extra inputs are not permitted", input: true}, ...]
 *
 * For forbidden-extras (the H1 case) we strip the `body.` prefix from `loc`
 * so the message reads "is_admin: Extra inputs are not permitted" — useful
 * for users who tampered with the request and hit the schema guard.
 *
 * Returns `null` if the body is not in the Pydantic shape (so the caller can
 * fall back to the raw `e.message`).
 */
export function parsePydanticFieldErrors(message: string): Record<string, string> | null {
  try {
    // ApiError.message is the raw `detail` value (a JSON string of the array,
    // or a string if the backend returned a flat error). Try parse first.
    const parsed = JSON.parse(message)
    if (!Array.isArray(parsed)) return null
    const out: Record<string, string> = {}
    for (const item of parsed) {
      if (!item || typeof item !== 'object') continue
      const loc = Array.isArray(item.loc) ? item.loc : []
      // Drop leading "body" / "query" / etc. — the visible field is the tail.
      const visibleLoc = loc.filter((p: unknown) => p !== 'body' && p !== 'query' && p !== 'path')
      const field = visibleLoc.join('.') || 'request'
      const msg = typeof item.msg === 'string' ? item.msg : 'Invalid value'
      out[field] = msg
    }
    return Object.keys(out).length > 0 ? out : null
  } catch {
    return null
  }
}
