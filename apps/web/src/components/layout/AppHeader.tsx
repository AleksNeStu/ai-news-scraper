import type { Route } from 'next'
import { Suspense } from 'react'
import { Languages, Newspaper, Search, Rss, Settings, Sparkles } from 'lucide-react'
import { getTranslations } from 'next-intl/server'
import { Link } from '@/i18n/navigation'
import { CommandPalette } from '@/components/CommandPalette'
import { NotificationBell } from '@/components/NotificationBell'
import { LogoutButton } from '@/components/auth/LogoutButton'
import { LocaleSwitcher } from '@/components/LocaleSwitcher'

/**
 * Global app header. Server component (only renders JSX; the bell +
 * locale switcher are small client islands). Used by the dashboard root
 * page and the (app) route group layout so the nav + bell stay in sync
 * everywhere.
 *
 * Nav labels come from `getTranslations('Header.nav')` so each render
 * resolves them in the request's active locale. The brand string lives
 * under the `Common` namespace (`appName`) so the brand stays in one
 * place across the header AND any future footers / email templates.
 *
 * The href values stay as canonical paths (`/articles`, `/dashboard/brief`).
 * Next.js's plain `next/link` resolves them against the current segment,
 * which under the `[locale]` layout means the user stays on the same
 * active locale. The LocaleSwitcher handles the explicit locale change.
 */
export async function AppHeader() {
  const t = await getTranslations('Header')
  const common = await getTranslations('Common')
  return (
    <header className="border-b border-border bg-canvas">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2">
          <Newspaper className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-semibold tracking-tight">{common('appName')}</h1>
        </div>
        <nav aria-label="Primary" className="flex items-center gap-1">
          <NavLink href="/scrape" icon={<Newspaper className="h-4 w-4" />}>
            {t('nav.scrape')}
          </NavLink>
          <NavLink href="/search" icon={<Search className="h-4 w-4" />}>
            {t('nav.search')}
          </NavLink>
          <NavLink href="/articles" icon={<Newspaper className="h-4 w-4" />}>
            {t('nav.articles')}
          </NavLink>
          <NavLink href="/dashboard/brief" icon={<Newspaper className="h-4 w-4" />}>
            {t('nav.brief')}
          </NavLink>
          <NavLink href="/feeds" icon={<Rss className="h-4 w-4" />}>
            {t('nav.feeds')}
          </NavLink>
          <NavLink href="/embeddings" icon={<Sparkles className="h-4 w-4" />}>
            {t('nav.embeddings')}
          </NavLink>
          <NavLink href="/settings" icon={<Settings className="h-4 w-4" />}>
            {t('nav.settings')}
          </NavLink>
          <CommandPalette />
          {/* LocaleSwitcher uses useSearchParams() — Next.js 15's
              static-prerender rule requires a Suspense boundary around
              any client component that calls the hook. Same pattern
              used in app/[locale]/unsubscribe/page.tsx for
              UnsubscribeForm. The fallback is a non-interactive
              placeholder so the prerender doesn't fail. */}
          <Suspense fallback={<LocaleSwitcherFallback />}>
            <LocaleSwitcher />
          </Suspense>
          <NotificationBell />
          <LogoutButton />
        </nav>
      </div>
    </header>
  )
}

function NavLink({
  href,
  icon,
  children,
}: {
  href: string
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Link
      href={href as Route}
      // min-w-24 (6rem / 96px) + justify-center keeps the nav
      // row visually consistent regardless of label length
      // ("Feeds" is 5 chars, "Articles" is 8 -- without a
      // min-width the buttons fan out at the top of the bar, which
      // reads as a misalignment on a polished header).
      className="inline-flex min-w-24 items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-surface hover:text-foreground"
    >
      {icon} {children}
    </Link>
  )
}

/** Non-interactive placeholder shown during Suspense fallback for the
 * LocaleSwitcher — keeps the header layout stable while Next streams
 * the locale-aware client island. The aria-label and Languages icon
 * are preserved so screen readers announce the same control name. */
function LocaleSwitcherFallback() {
  return (
    <span
      aria-label="Language switcher"
      className="inline-flex items-center gap-1 text-sm text-muted-foreground"
    >
      <Languages className="h-4 w-4" aria-hidden="true" />
      <span className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground/50">
        …
      </span>
    </span>
  )
}
