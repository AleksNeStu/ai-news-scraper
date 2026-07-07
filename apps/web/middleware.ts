import createMiddleware from 'next-intl/middleware'
import { NextResponse, type NextRequest } from 'next/server'
import { routing } from '@/i18n/routing'

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
    return intlResponse
  }

  const token = req.cookies.get('auth_token')?.value
  if (!token) {
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
