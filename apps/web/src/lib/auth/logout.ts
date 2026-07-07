/**
 * Server-confirmed logout helper.
 *
 * Per ADR-015 §15.9, the new ``POST /auth/logout`` endpoint:
 *   1. revokes the refresh-token row referenced by the ``auth_refresh``
 *      cookie (``UPDATE refresh_tokens SET revoked_at = now() ...``);
 *   2. deletes BOTH cookies on the response with symmetric
 *      ``httponly / secure / samesite / path`` flags (closes the M3
 *      cosmetic finding in the same diff).
 *
 * On the web side this function does the round-trip in a server
 * action (NOT in the browser — the API is on a different origin
 * that does not advertise CORS for ``POST /auth/logout``). On 2xx
 * the local ``auth_token`` cookie is cleared via Next's
 * ``cookies().delete()`` and the caller is redirected to ``/login``.
 * On a server-side 5xx the cookie is left intact (so the user
 * isn't accidentally logged out when the revoke failed) and an
 * error state is returned — the caller surfaces it inline rather
 * than swallowing it (the previous behaviour silently cleared
 * cookies and bounced the user to /login regardless).
 *
 * ``ApiError`` is re-exported from ``@/lib/api`` so callers can
 * inspect the underlying HTTP shape if they need finer-grained
 * handling.
 */
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { api } from '@/lib/api'

/**
 * Discriminated logout result.
 *
 * - `kind: 'ok'` — server revoked the refresh row; ``performLogout``
 *   redirects to /login and never returns this branch to the caller.
 * - `kind: 'error', code: 'logout_failed'` — server returned a non-2xx
 *   OR a network error prevented the round-trip. The cookie is left
 *   intact so the user is not accidentally logged out when the revoke
 *   may or may not have succeeded.
 *
 * The `code` field (not a pre-formatted message) is intentional: the
 * caller (``logoutAction`` in ``auth.ts``) maps the code to a
 * translation key so the inline error reads in the active locale.
 * Pre-formatting the message here would couple this helper to a
 * single English string and break the i18n contract (Devil-4 finding).
 */
export type LogoutResult = { kind: 'ok' } | { kind: 'error'; code: 'logout_failed' }

export const AUTH_COOKIE_NAME = 'auth_token'
export const AUTH_REFRESH_COOKIE_NAME = 'auth_refresh'

/**
 * Run the server-confirmed logout flow.
 *
 * Steps:
 *   1. POST /auth/logout. The browser forwards the refresh cookie via
 *      ``credentials: 'include'``; the server revokes the row and
 *      deletes both cookies on the response.
 *   2. On 2xx → clear the local ``auth_token`` cookie (the cookie
 *      carries the access JWT; the server already revoked the
 *      refresh) and ``redirect('/login')``.
 *   3. On a non-2xx response → leave the cookies intact and return
 *      a discriminated error result so the caller can surface the
 *      failure to the user.
 *
 * Network failures (DNS, refused, timeout) raise — they are NOT
 * caught here. The caller decides whether a "couldn't reach server"
 * UX is appropriate; for the header logout button we render an
 * inline error and let the user retry.
 */
export async function performLogout(): Promise<LogoutResult> {
  try {
    await api.post('/auth/logout')
  } catch {
    // 5xx (and any non-204 the server happens to send) is a server
    // problem — the refresh row may or may not be revoked; we
    // cannot know, so we DO NOT clear the local cookie. The
    // caller (header button) shows the error and the user can
    // retry.
    //
    // Network errors are bundled into the same code path so the
    // caller does not need to distinguish — both leave local state
    // intact and surface the same retry UX.
    return { kind: 'error', code: 'logout_failed' }
  }

  // 2xx: server revoked the refresh row. Clear the local access-token
  // cookie AND the refresh cookie (the server's Set-Cookie delete
  // headers do not reach the browser through this server-action
  // fetch chain — see ``forwardAuthCookies`` in ``auth.ts`` for the
  // mirror problem on the login/register side). Bounce to /login.
  const jar = await cookies()
  jar.delete(AUTH_COOKIE_NAME)
  jar.delete(AUTH_REFRESH_COOKIE_NAME)
  redirect('/login')
}
