'use server'

import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { api, ApiError } from './api'

const COOKIE_NAME = 'auth_token'
const COOKIE_MAX_AGE = 60 * 60 * 24 // 1d mirror of API

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

export async function loginAction(_prev: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get('email') ?? '')
  const password = String(formData.get('password') ?? '')
  try {
    const res = await api.post<{ user: unknown; token: string }>('/auth/login', { email, password })
    ;(await cookies()).set(COOKIE_NAME, res.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: COOKIE_MAX_AGE,
    })
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
          error: `Too many attempts. Try again in ${retryAfter} second${retryAfter === 1 ? '' : 's'}.`,
        }
      }
      return { ok: false, error: e.message }
    }
    return { ok: false, error: 'Login failed' }
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
  formData: FormData
): Promise<RegisterState> {
  const email = String(formData.get('email') ?? '')
  const password = String(formData.get('password') ?? '')
  try {
    const res = await api.post<{ user: unknown; token: string }>('/auth/register', {
      email,
      password,
    })
    ;(await cookies()).set(COOKIE_NAME, res.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: COOKIE_MAX_AGE,
    })
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
    return { ok: false, error: 'Registration failed' }
  }
}

/**
 * Server-action logout. Calls `/auth/logout` first (which revokes the
 * refresh token server-side per ADR-015 §15.9), then on 2xx clears the
 * cookie and redirects to `/login`. On a server-side 5xx the cookie is
 * left intact and the action returns an error state — the caller (header
 * logout button) surfaces the failure to the user instead of silently
 * swallowing it.
 */
export async function logoutAction(): Promise<{ ok: false; error: string }> {
  // Pre-H3 implementation: cookie-only clear. H3 ships in the next
  // commit and replaces this with a server-confirmed flow.
  ;(await cookies()).delete(COOKIE_NAME)
  redirect('/login')
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
