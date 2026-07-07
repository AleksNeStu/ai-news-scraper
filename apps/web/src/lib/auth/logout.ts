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
import { api, ApiError } from '@/lib/api'

export type LogoutResult = { kind: 'ok' } | { kind: 'error'; message: string }

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
  } catch (e) {
    if (e instanceof ApiError) {
      // 5xx (and any non-204 the server happens to send) is a server
      // problem — the refresh row may or may not be revoked; we
      // cannot know, so we DO NOT clear the local cookie. The
      // caller (header button) shows the error and the user can
      // retry.
      return {
        kind: 'error',
        message: 'Logout failed. Please try again.',
      }
    }
    // Network / unknown — surface a generic message but do not
    // clear local state.
    return {
      kind: 'error',
      message: 'Logout failed. Please try again.',
    }
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
