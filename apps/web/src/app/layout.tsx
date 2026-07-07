import type { Metadata } from 'next'
import './globals.css'

/**
 * Pass-through root layout.
 *
 * Per the Task #32 plan, the actual `<html>` + `<body>` owner is the
 * new `[locale]/layout.tsx`, which sets `<html lang={locale}>` so the
 * `<html lang="en">` hardcoding on the old root layout (the bug Task
 * #32 fixes) goes away.
 *
 * We keep this file (instead of deleting it) because Next.js's App
 * Router REQUIRES a root `app/layout.tsx`. Removing it crashes
 * `next build` with "missing root layout". So we keep it as a
 * transparent passthrough.
 *
 * Frontend (the next teammate) will:
 *   1. Add `params: { locale: string }` typing in `[locale]/layout.tsx`
 *      and the full NextIntlClientProvider wrapper.
 *   2. Verify this passthrough + the new locale layout chain correctly
 *      during the locale-switcher smoke tests.
 *
 * Note on metadata: `metadata.title` / `description` were on this
 * file. The locale-aware layout should override these via the
 * `generateMetadata` API. For now we keep them so the Sentry wizard
 * build doesn't blow up.
 */
export const metadata: Metadata = {
  title: 'AI News Search',
  description: 'Scrape, summarize, and semantically search your personal news library.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return children
}