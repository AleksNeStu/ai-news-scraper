import type messages from './messages/en.json'
import type { routing } from './i18n/routing'

/**
 * Module augmentation for next-intl's `AppConfig` (Task #32).
 *
 * This is the canonical type-safe pattern recommended in the
 * next-intl 4.x docs (replaces the older `IntlMessages` global
 * augmentation). By pointing the augmentation at `./messages/en.json`:
 *
 *   - `useTranslations('Articles.Toolbar')` is autocompleted.
 *   - `t('summary')` inside that namespace fails at compile time if
 *     the key is missing from en.json — typos become build errors.
 *   - ICU placeholders are typed: `t('count', { count: 5 })` checks
 *     that `count` is referenced in the message string.
 *
 * We use `en.json` (NOT a hand-written type) so the augmentation
 * stays in sync with whatever the frontend ships in that file.
 * Translation parity (en === ru) is verified separately by the
 * Analyst role in `.agent/docs/i18n-coverage.md`.
 *
 * `Locale` is derived from `routing.locales` so adding a new locale
 * is a one-line change in `i18n/routing.ts`.
 */
declare module 'next-intl' {
  interface AppConfig {
    Locale: (typeof routing.locales)[number]
    Messages: typeof messages
  }
}
