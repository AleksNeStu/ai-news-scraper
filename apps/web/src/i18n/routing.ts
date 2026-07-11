import { defineRouting } from 'next-intl/routing'

/**
 * Locale routing configuration for next-intl (Task #32, revisited in Task #66).
 *
 * - Locales: ['en', 'ru'] — en + ru baseline per PRD.
 * - localePrefix: 'always' — EVERY URL is prefixed with the active
 *   locale (`/en/login`, `/ru/login`). No bare `/login` URLs anymore.
 *   Rationale: with `'as-needed'`, next-intl middleware issued a 307
 *   from `/en/X` → `/X` for the default locale (because `/en/` was
 *   treated as a superfluous prefix on the English path), and the
 *   compose middleware in `apps/web/src/middleware.ts` then ran on
 *   the resulting `/X` URL — which, on bare public routes like
 *   `/login`, produced a 307 back into the locale-prefixed form when
 *   the auth check needed to build a redirect target. That
 *   `/en/login` ↔ `/login` ping-pong is what surfaced as
 *   `ERR_TOO_MANY_REDIRECTS` on every a11y-audit route.
 *   Switching to `'always'` makes `/en/X` the canonical form for the
 *   default locale (no redirect), and any bare `/X` gets a single
 *   307 → `/en/X` on first hit. No loop.
 * - alternateLinks: true — next-intl middleware emits the `Link` HTTP
 *   response header AND `<link rel="alternate" hreflang>` tags for every
 *   page automatically (one less thing the sitemap needs to do by hand).
 *
 * Consumers import `routing` from `@/i18n/routing`. Do NOT mutate the
 * `locales` array at runtime; it feeds both `defineRouting` and the
 * `hasLocale()` type guard.
 */
export const routing = defineRouting({
  locales: ['en', 'ru'],
  defaultLocale: 'en',
  localePrefix: 'always',
  alternateLinks: true,
})
