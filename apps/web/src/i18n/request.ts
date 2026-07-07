import { hasLocale } from 'next-intl'
import { getRequestConfig } from 'next-intl/server'
import { routing } from './routing'

/**
 * Per-request i18n config (Task #32).
 *
 * Loaded by `next-intl` on every Server Component / Server Action render
 * to attach the right message catalog + locale-aware formatters.
 *
 * Design notes:
 *   - `timeZone: 'UTC'` keeps SSR output deterministic across server
 *     restarts; the date in `formatLongDate()` (briefs) is already a
 *     UTC date, so this matches the data semantics.
 *   - `now: undefined` (intentionally omitted) lets `useFormatter` use
 *     the request time. If a relative-time leak ever surfaces in
 *     hydration, pin `now: new Date()` to the request start.
 *   - Messages are loaded via dynamic `import()` so each locale JSON
 *     file becomes its own webpack chunk — en.json stays in the initial
 *     bundle for SSR, ru.json splits off.
 *   - Locale validation uses `hasLocale(routing.locales, requested)`,
 *     the canonical guard from next-intl 4.x (replaces the deprecated
 *     locale-existence check that used to live in user code).
 */
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
    timeZone: 'UTC',
  }
})
