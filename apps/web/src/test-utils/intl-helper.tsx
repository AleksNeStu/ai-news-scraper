/**
 * Shared test helper for components and pages that consume next-intl.
 *
 * All client-component test files that render anything using
 * `useTranslations`, `useLocale`, `useFormatter`, or `<Link>` from
 * `@/i18n/navigation` MUST wrap the rendered tree in this helper. The
 * NextIntlClientProvider must receive:
 *   - the same locale the component thinks it's in (`locale`)
 *   - the matching messages catalog (loaded synchronously via a static
 *     import so vitest doesn't need the dynamic loader)
 *
 * Default locale is `en` because every existing assertion in the test
 * suite targets English copy. Russian copy is verified separately by
 * the Analyst's coverage matrix.
 */

import { NextIntlClientProvider } from 'next-intl'
import type { ReactNode } from 'react'
import enMessages from '@/messages/en.json'
import ruMessages from '@/messages/ru.json'

export interface IntlWrapperOpts {
  locale?: 'en' | 'ru'
  messages?: Record<string, unknown>
}

const CATALOG: Record<'en' | 'ru', Record<string, unknown>> = {
  en: enMessages,
  ru: ruMessages,
}

export function IntlWrapper({
  children,
  locale = 'en',
  messages,
}: IntlWrapperOpts & { children: ReactNode }) {
  const messages_ = (messages ?? CATALOG[locale]) as Parameters<
    typeof NextIntlClientProvider
  >[0]['messages']
  return (
    <NextIntlClientProvider locale={locale} messages={messages_}>
      {children}
    </NextIntlClientProvider>
  )
}
