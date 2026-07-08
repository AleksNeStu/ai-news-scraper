import { AppHeader } from '@/components/layout/AppHeader'

/**
 * App-group layout: header + main content for authenticated routes
 * (search, articles, dashboard, scrape, feeds, settings).
 *
 * A11y: the first focusable element is the skip-link to `#main`,
 * satisfying WCAG 2.4.1 Bypass Blocks. The `<main>` element receives
 * `id="main"` and `tabIndex={-1}` so the link target is focusable but
 * not part of the regular Tab order.
 *
 * Closes a11y audit #7.
 */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to main content
      </a>
      <main id="main" tabIndex={-1} className="min-h-screen">
        <AppHeader />
        {children}
      </main>
    </>
  )
}
