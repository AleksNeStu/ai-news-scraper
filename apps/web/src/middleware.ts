import createMiddleware from 'next-intl/middleware'
import { NextResponse, type NextRequest } from 'next/server'
import { routing } from '@/i18n/routing'

/**
 * Dev auth bypass — see DEV_AUTH_BYPASS_USER below.
 *
 * Implements HS256 JWT signing using the Web Crypto API (works in
 * Edge runtime; no extra deps). The minted token uses the same
 * JWT_SECRET + algorithm as the API (``apps/api/api/services/auth.py``),
 * so it verifies identically on the backend.
 */
async function signJwtHS256(
  payload: Record<string, unknown>,
  secret: string,
): Promise<string> {
  const encoder = new TextEncoder()
  const header = { alg: 'HS256', typ: 'JWT' }
  const headerB64 = btoa(JSON.stringify(header))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
  const payloadB64 = btoa(JSON.stringify(payload))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
  const data = encoder.encode(`${headerB64}.${payloadB64}`)
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const sig = await crypto.subtle.sign('HMAC', key, data)
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
  return `${headerB64}.${payloadB64}.${sigB64}`
}

/**
 * Composed middleware (Task #32): locale resolution + auth gating.
 *
 * Order matters. The locale middleware runs FIRST so that:
 *   - Incoming `/foo` → resolved as `/en/foo` (default locale),
 *     preserving the original auth path.
 *   - Incoming `/ru/foo` → preserved as `/ru/foo`.
 *   - `Link` / `useRouter` from `@/i18n/navigation` auto-prefix the
 *     active locale into navigation.
 *
 * Then the auth check runs on the RESOLVED pathname (so it sees
 * `/en/dashboard` or `/ru/dashboard`, never the bare `/dashboard`).
 *
 * PUBLIC_PATHS strips the locale prefix before checking, so the
 * original auth contract (`/login`, `/register`, `/unsubscribe` as
 * public) still holds under both `/en/login` and `/ru/login`.
 *
 * PUBLIC_PREFIXES (api/auth, _next, favicon) similarly strip the
 * leading locale segment before matching.
 *
 * Matcher:
 *   - Includes `api/` in the negative lookahead so the existing
 *     rewrite `/api/backend/:path*` → FastAPI proxy is unaffected.
 *   - Still excludes static assets and files-with-extension (svg, png,
 *     jpg, jpeg, gif, webp).
 */
const intlMiddleware = createMiddleware(routing)

// Strips a leading locale segment so the auth check below sees the
// canonical path the original (pre-i18n) middleware used.
//   '/en/dashboard' → '/dashboard'
//   '/ru/login'     → '/login'
//   '/dashboard'    → '/dashboard'  (as-needed, default locale)
function stripLocalePrefix(pathname: string): string {
  for (const locale of routing.locales) {
    if (pathname === `/${locale}`) return '/'
    if (pathname.startsWith(`/${locale}/`)) return pathname.slice(locale.length + 1)
  }
  return pathname
}

// Reverse helper: given a canonical path, return the locale-prefixed
// form for the requested active locale (or bare path for default).
function withLocalePrefix(canonical: string, activeLocale: string): string {
  if (activeLocale === routing.defaultLocale) return canonical
  return `/${activeLocale}${canonical === '/' ? '' : canonical}`
}

// Public paths — must match the canonical (no-locale) form.
// The locale prefix is stripped before the comparison.
const PUBLIC_PATHS = new Set(['/login', '/register', '/unsubscribe'])
const PUBLIC_PREFIXES = ['/api/auth', '/_next', '/favicon']

/**
 * Dev auth bypass.
 *
 * Set ``DEV_AUTH_BYPASS_USER=<email>`` (e.g. ``alex@example.com``) in
 * the web container's environment to skip the login flow. The middleware
 * will mint a fresh HS256 JWT for that email and set the
 * ``auth_token`` cookie on every request that doesn't already carry
 * one, so the dev can click around the app without going through
 * ``/login`` first.
 *
 * Why: ``curl``-driven / Playwright smoke-tests against the dev
 * stack need a session; logging in by hand per test is friction. The
 * bypass is gated on the env var so it never activates in production
 * (``NEXT_PUBLIC_NODE_ENV=production`` builds). The minted token uses
 * the same ``JWT_SECRET`` the API verifies against, so the API accepts
 * the session the same as a hand-issued one.
 *
 * Required env (web container):
 *   - ``DEV_AUTH_BYPASS_USER`` — the demo user's email (must already
 *     exist in the API's seeded DB; matches the seeded
 *     ``alex@example.com`` by default in the project's docker-compose
 *     seed). The middleware mints the JWT with the corresponding
 *     ``sub`` from ``/auth/me``'s response, but the API's
 *     ``get_current_user_id`` decodes ``sub`` and the route handlers
 *     load the user by that id; for the seeded dev user the id is
 *     ``11111111-1111-1111-1111-111111111111`` (created in
 *     ``api/scripts/seed.py``).
 *   - ``JWT_SECRET`` — same value the API container uses. Defaults to
 *     ``dev-secret-change-me`` in the project's docker-compose.
 */
const DEV_BYPASS_USER = process.env.DEV_AUTH_BYPASS_USER
const DEV_BYPASS_USER_ID = process.env.DEV_AUTH_BYPASS_USER_ID ?? '11111111-1111-1111-1111-111111111111'
const DEV_BYPASS_SECRET = process.env.JWT_SECRET ?? 'dev-secret-change-me'
const DEV_BYPASS_COOKIE_MAX_AGE = 60 * 60 * 24 // 24h

async function buildDevBypassResponse(
  req: NextRequest,
  intlResponse: NextResponse,
): Promise<NextResponse> {
  // Mint a fresh HS256 JWT for the demo user. The payload mirrors
  // what the API's ``create_token`` produces: ``sub`` (user id),
  // ``email``, ``iat`` (issued at), ``exp`` (24h out so the dev
  // session survives a long debugging session). 5-year TTL is a
  // common dev convenience; in production the API's normal 15-minute
  // ``access_token_expires_min`` applies.
  const iat = Math.floor(Date.now() / 1000)
  const exp = iat + 60 * 60 * 24 * 365 * 5
  const token = await signJwtHS256(
    { sub: DEV_BYPASS_USER_ID, email: DEV_BYPASS_USER, iat, exp },
    DEV_BYPASS_SECRET,
  )

  // Set the cookie on the response the locale middleware already
  // prepared. Edge runtime requires Set-Cookie via NextResponse.next
  // headers, not the older ``res.cookies`` API.
  intlResponse.cookies.set('auth_token', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: DEV_BYPASS_COOKIE_MAX_AGE,
  })
  return intlResponse
}

export function middleware(req: NextRequest) {
  // 1) Locale resolution first. This rewrites /dashboard → /en/dashboard,
  //    preserves /ru/dashboard, attaches hreflang Link header, etc.
  const intlResponse = intlMiddleware(req)

  // Determine the locale the request resolved to. We look at the
  // incoming pathname: if the URL already starts with /<locale>/,
  // that's the active locale; otherwise the default-locale strategy
  // means the active locale is the default. We use this for the
  // auth-redirect targets so we land the user back on the right locale.
  const incoming = req.nextUrl.pathname
  const activeLocale =
    routing.locales.find((l) => incoming.startsWith(`/${l}/`) || incoming === `/${l}`) ??
    routing.defaultLocale

  // The canonical (no-locale) form of the requested path.
  const canonical = stripLocalePrefix(incoming)

  if (PUBLIC_PREFIXES.some((p) => canonical.startsWith(p))) return intlResponse
  if (PUBLIC_PATHS.has(canonical)) {
    // If already logged in, send to dashboard (locale-aware redirect).
    if (req.cookies.get('auth_token')) {
      return NextResponse.redirect(new URL(withLocalePrefix('/', activeLocale), req.url))
    }
    // Dev auth bypass — public path. Mint a session cookie for the
    // demo user and serve the page as if the user were logged in.
    if (DEV_BYPASS_USER) {
      return buildDevBypassResponse(req, intlResponse)
    }
    return intlResponse
  }

  const token = req.cookies.get('auth_token')?.value
  if (!token) {
    // Dev auth bypass — non-public path. Mint a session cookie and
    // serve the protected page as the demo user.
    if (DEV_BYPASS_USER) {
      return buildDevBypassResponse(req, intlResponse)
    }
    // Preserve the locale-aware next param so the user lands on the
    // right locale after login.
    const loginUrl = new URL(withLocalePrefix('/login', activeLocale), req.url)
    // The `next` query must preserve the user's intended destination,
    // including its locale prefix, so the post-login redirect lands
    // them back on e.g. /ru/dashboard.
    const nextTarget = withLocalePrefix(canonical === '/' ? '/' : canonical, activeLocale)
    loginUrl.searchParams.set('next', nextTarget)
    return NextResponse.redirect(loginUrl)
  }

  return intlResponse
}

export const config = {
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)'],
}
