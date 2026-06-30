import Link from 'next/link'
import { Newspaper, Search, Rss, Settings, LogOut } from 'lucide-react'
import { logoutAction } from '@/lib/auth'
import { NotificationBell } from '@/components/NotificationBell'

/**
 * Global app header. Server component (only renders JSX; the bell child is
 * a small client island). Used by the dashboard root page and the (app) route
 * group layout so the nav + bell stay in sync everywhere.
 */
export function AppHeader() {
  return (
    <header className="border-b border-border bg-canvas">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2">
          <Newspaper className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-semibold tracking-tight">AI News Search</h1>
        </div>
        <nav className="flex items-center gap-1">
          <NavLink href="/scrape" icon={<Newspaper className="h-4 w-4" />}>
            Scrape
          </NavLink>
          <NavLink href="/search" icon={<Search className="h-4 w-4" />}>
            Search
          </NavLink>
          <NavLink href="/articles" icon={<Newspaper className="h-4 w-4" />}>
            Articles
          </NavLink>
          <NavLink href="/dashboard/brief" icon={<Newspaper className="h-4 w-4" />}>
            Brief
          </NavLink>
          <NavLink href="/feeds" icon={<Rss className="h-4 w-4" />}>
            Feeds
          </NavLink>
          <NavLink href="/settings" icon={<Settings className="h-4 w-4" />}>
            Settings
          </NavLink>
          <NotificationBell />
          <form action={logoutAction}>
            <button className="ml-2 inline-flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-primary/40">
              <LogOut className="h-4 w-4" /> Logout
            </button>
          </form>
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
      href={href}
      className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-surface hover:text-foreground"
    >
      {icon} {children}
    </Link>
  )
}
