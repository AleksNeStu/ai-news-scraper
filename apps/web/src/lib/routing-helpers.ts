/**
 * Locale-prefix helpers shared between the composed middleware and
 * unit tests (Task #66).
 *
 * These are intentionally plain functions (no Next.js / Edge runtime
 * imports) so they can be unit-tested under Node + vitest without
 * standing up the full Next.js dev server.
 *
 * Under ``localePrefix: 'always'`` (Task #66) EVERY locale gets the
 * ``/<locale>...`` form on the wire — including the default locale.
 * Before Task #66 the bare-path short-circuit for the default locale
 * was a source of an infinite redirect loop on the a11y CI gate.
 */

import { routing } from '@/i18n/routing'

// Strips a leading locale segment so the auth check in middleware.ts
// sees the canonical path the original (pre-i18n) middleware used.
//   '/en/dashboard'  → '/dashboard'
//   '/ru/login'      → '/login'
//   '/en'            → '/'
//   '/dashboard'     → '/dashboard'  (no locale — defensive fallback)
export function stripLocalePrefix(pathname: string): string {
  for (const locale of routing.locales) {
    if (pathname === `/${locale}`) return '/'
    if (pathname.startsWith(`/${locale}/`)) return pathname.slice(locale.length + 1)
  }
  return pathname
}

// Reverse helper: given a canonical path, return the locale-prefixed
// form for the requested active locale. Under `localePrefix: 'always'`
// EVERY locale — including the default — gets the `/<locale>...` form,
// so the bare-path short-circuit for the default locale is removed.
//   withLocalePrefix('/login', 'en') → '/en/login'
//   withLocalePrefix('/login', 'ru') → '/ru/login'
//   withLocalePrefix('/', 'en')      → '/en'
//   withLocalePrefix('/', 'ru')      → '/ru'
export function withLocalePrefix(canonical: string, activeLocale: string): string {
  return `/${activeLocale}${canonical === '/' ? '' : canonical}`
}

/**
 * Validate a `next` query-param target for post-login redirect.
 * (Task #67) Returns a safe same-origin relative path, or `/` on rejection.
 *
 * Rejects (returns `/`):
 *   - non-string input (null, undefined, numbers, objects, arrays)
 *   - empty / whitespace-only
 *   - absolute URLs (`http://...`, `https://...`)
 *   - protocol-relative URLs (`//evil.com/...`) — browsers resolve these
 *     against the page's scheme; attacker-controlled host
 *   - backslash variants (`/\\evil.com`, `\\\\evil.com`) — some browsers
 *     normalize `\` to `/` in URL contexts, so a `//` written with backslashes
 *     can sneak past a naive startsWith('/') check
 *   - anything not starting with `/` (e.g. `javascript:alert(1)`,
 *     `evil.com/foo`)
 *
 * Accepts (returns the trimmed value):
 *   - `/`, `/en`, `/en/dashboard`, `/ru/articles/123`
 *   - `/../../admin` — relative traversal is the consumer's policy, not ours;
 *     the path itself stays same-origin so a browser-side navigation lands on
 *     an app-internal route, not an attacker host.
 *
 * Threat model + ADR: see `.agent/adr/021-open-redirect-prevention.md` (local-only).
 * AC checklist: see `docs/security/open-redirect-next-param.md`.
 */
export function validateNextTarget(input: unknown): string {
  if (typeof input !== 'string') return '/'
  const v = input.trim()
  if (!v) return '/'
  if (!v.startsWith('/')) return '/'
  if (v.startsWith('//')) return '/'
  if (v.startsWith('/\\')) return '/'
  if (v.startsWith('\\\\')) return '/'
  return v
}
