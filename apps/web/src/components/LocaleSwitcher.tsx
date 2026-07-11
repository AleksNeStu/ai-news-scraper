'use client'

/**
 * LocaleSwitcher — header-level language picker (Task #32).
 *
 * Small client island embedded inside the AppHeader (a server component).
 * Switching locales MUST preserve the current pathname + search params
 * so a user deep in /articles?page=2 lands back on /ru/articles?page=2,
 * not the bare home page of the new locale.
 *
 * Routing:
 *   - `useLocale()`     — current locale, sourced from the request-scoped
 *                          next-intl context (set in [locale]/layout.tsx).
 *   - `usePathname()`    — locale-aware wrapper from @/i18n/navigation
 *                          (returns the canonical path WITHOUT the prefix,
 *                          e.g. `/articles` even on `/ru/articles`).
 *   - `useRouter()`      — locale-aware wrapper; `router.replace(path, { locale })`
 *                          navigates to the SAME path under the new locale,
 *                          correctly emitting the `/<locale>` prefix
 *                          for both `en` and `ru` (localePrefix:
 *                          'always').
 *
 * UI:
 *   - A <select> for accessibility (native keyboard, screen-reader
 *     announcement). Hidden visual chrome (the `<Languages>` icon) hints
 *     at the control's purpose without competing with the nav.
 *   - `aria-label` on the select itself describes the action in the
 *     active locale ("Switch language" / "Сменить язык").
 */

import { useTransition } from 'react'
import { useSearchParams } from 'next/navigation'
import { Languages } from 'lucide-react'
import { useLocale, useTranslations } from 'next-intl'
import { usePathname, useRouter } from '@/i18n/navigation'
import { routing } from '@/i18n/routing'

export function LocaleSwitcher() {
  const locale = useLocale()
  const router = useRouter()
  const pathname = usePathname()
  const search = useSearchParams()
  const t = useTranslations('LocaleSwitcher')
  const [pending, startTransition] = useTransition()

  function onChange(next: string) {
    if (next === locale) return
    startTransition(() => {
      // Preserve the current search params so a user deep in
      // `/articles?page=2&tier=must_read` lands back on the same
      // position under the new locale, not the bare list root.
      // The wrapped `usePathname()` from @/i18n/navigation returns
      // the locale-stripped canonical form, so we forward it verbatim
      // and let next-intl re-prefix based on `next`.
      const query = search ? Object.fromEntries(search.entries()) : {}
      // `next` is the `<select>` value (typed `string`). It only ever
      // carries one of `routing.locales` because the `<option>` list
      // is generated from that array, so the cast is safe at runtime.
      router.replace({ pathname, query }, { locale: next as 'en' | 'ru' })
    })
  }

  return (
    <label className="inline-flex items-center gap-1 text-sm text-muted-foreground">
      <Languages className="h-4 w-4" aria-hidden="true" />
      <select
        value={locale}
        onChange={(e) => onChange(e.target.value)}
        disabled={pending}
        aria-label={t('label')}
        className="cursor-pointer rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground focus:border-primary focus:outline-none disabled:opacity-50"
      >
        {routing.locales.map((l) => (
          <option key={l} value={l}>
            {t(l as 'en' | 'ru')}
          </option>
        ))}
      </select>
    </label>
  )
}
