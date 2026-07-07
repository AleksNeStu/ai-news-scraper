import { defineRouting } from 'next-intl/routing'

/**
 * Locale routing configuration for next-intl (Task #32).
 *
 * - Locales: ['en', 'ru'] — en + ru baseline per PRD.
 * - localePrefix: 'as-needed' — default locale (`en`) renders at bare paths
 *   (`/articles`); non-default locales (`ru`) render under prefix
 *   (`/ru/articles`). Keeps marketing URLs clean while making Russian
 *   first-class.
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
  localePrefix: 'as-needed',
  alternateLinks: true,
})
