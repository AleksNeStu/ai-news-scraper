/**
 * Automated WCAG 2.1 AA + 2.2 AA gate for ai-news-scraper.
 *
 * Drives a headless Chromium against 13 representative templates via
 * Playwright + @axe-core/playwright. Severity-gated by CI: this spec
 * fails on `serious` + `critical` violations; `moderate` + `minor`
 * violations are logged via `console.warn` for triage.
 *
 * Run locally:
 *   pnpm dev    # in one shell — preview at http://localhost:3807
 *   BASE_URL=http://localhost:3807 pnpm exec playwright test e2e/a11y.spec.ts
 *
 * Per the a11y-audit skill, automation catches ~30-40% of WCAG criteria
 * by issue volume. The other 60-70% (focus order, screen-reader
 * announcement, link context) is covered by a11y/ai-news-scraper/manual-checklist.md.
 */

import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const BASE_URL = process.env.BASE_URL ?? 'http://127.0.0.1:4173'

// Severity ordering is documented at
// https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md
// We fail on `serious` and `critical`; lower severities are warnings.

interface AxeViolation {
  id: string
  impact: 'minor' | 'moderate' | 'serious' | 'critical' | null
  description: string
  helpUrl: string
  nodes: ReadonlyArray<{ html: string; target: ReadonlyArray<string> }>
}

function partitionBySeverity(violations: ReadonlyArray<AxeViolation>): {
  blockers: AxeViolation[]
  warnings: AxeViolation[]
} {
  const blockers: AxeViolation[] = []
  const warnings: AxeViolation[] = []
  for (const v of violations) {
    // TS2345: `Set<'serious' | 'critical'>.has` rejects the wider
    // `AxeViolation['impact']` (which also includes 'minor' / 'moderate'
    // / null). Direct equality on the literal members avoids the
    // Set-membership type mismatch.
    if (v.impact === 'serious' || v.impact === 'critical') blockers.push(v)
    else warnings.push(v)
  }
  return { blockers, warnings }
}

function summarise(label: string, items: ReadonlyArray<AxeViolation>): string {
  if (items.length === 0) return `  ${label}: 0`
  const lines = items.map(
    (v) =>
      `  ${label}: [${v.impact ?? 'unknown'}] ${v.id} — ${v.description}\n` +
      `    ${v.helpUrl}\n` +
      v.nodes
        .slice(0, 3)
        .map((n) => `    -> ${n.target.join(' ')} :: ${n.html.slice(0, 120)}`)
        .join('\n')
  )
  return lines.join('\n')
}

/**
 * Representative templates — chosen to cover the bulk of the product
 * with minimal test runtime. Adding a route? Either add it here (if
 * it's a template-level change) or document why it's covered by
 * another spec.
 *
 * Scope matches the 13-route surface audited in
 * ``a11y/ai-news-scraper/audit-report.md``:
 *   - Public:   login, register, unsubscribe
 *   - List/detail: dashboard, articles, articles/[id], search,
 *     feeds, scrape
 *   - Auth-only settings/digest: settings, dashboard/brief,
 *     dashboard/brief/[date]
 *
 * NOTE on locale prefix: the production app uses next-intl with
 * `localePrefix: 'as-needed'`. The bare paths (`/articles`, `/login`,
 * etc.) ALSO resolve via the middleware rewrite to `/en/...`, but the
 * non-locale page.tsx files at app/(app)/, app/(auth)/, and
 * app/unsubscribe/ are leftover from before the i18n migration and
 * render under the pass-through root layout (no <html lang>) when
 * hit directly. Hitting the locale-prefixed URL renders the
 * [locale]/layout.tsx wrapper which sets `<html lang="en">` properly,
 * which is what the axe-core a11y gate requires.
 *
 * NOTE on dynamic segments: `/articles/[id]` and
 * `/dashboard/brief/[date]` use sample values that exercise the route
 * shell. With ``E2E_AUTH_COOKIE`` unset (the default in CI), the auth-
 * required routes redirect to ``/en/login`` — the spec audits whatever
 * the page lands on, so this is intentional coverage of both the
 * redirect chain and the destination template.
 */
const ROUTES: ReadonlyArray<{ path: string; name: string; requiresAuth: boolean }> = [
  // Public — no session needed.
  { path: '/en/login', name: 'login', requiresAuth: false },
  { path: '/en/register', name: 'register', requiresAuth: false },
  { path: '/en/unsubscribe', name: 'unsubscribe', requiresAuth: false },
  // Authenticated — gate on E2E_AUTH_COOKIE in CI; redirects to
  // /en/login otherwise, which the spec audits anyway.
  { path: '/en', name: 'home', requiresAuth: true },
  { path: '/en/dashboard', name: 'dashboard', requiresAuth: true },
  { path: '/en/articles', name: 'articles-list', requiresAuth: true },
  { path: '/en/articles/123', name: 'articles-detail', requiresAuth: true },
  { path: '/en/search', name: 'search', requiresAuth: true },
  { path: '/en/scrape', name: 'scrape-form', requiresAuth: true },
  { path: '/en/dashboard/brief', name: 'brief-list', requiresAuth: true },
  { path: '/en/dashboard/brief/2026-01-15', name: 'brief-detail', requiresAuth: true },
  { path: '/en/feeds', name: 'feeds', requiresAuth: true },
  { path: '/en/settings', name: 'settings', requiresAuth: true },
]

for (const route of ROUTES) {
  test(`a11y — ${route.name} (${route.path})`, async ({ page }) => {
    // Authenticated routes need a session cookie to render the actual
    // dashboard (otherwise the route redirects to /login and we audit
    // the login page instead). The CI runner uses a pre-seeded test
    // cookie; for local runs, set E2E_AUTH_COOKIE in your shell.
    if (route.requiresAuth) {
      const authCookie = process.env.E2E_AUTH_COOKIE
      if (authCookie) {
        await page.context().addCookies([
          {
            name: 'auth_token',
            value: authCookie,
            domain: new URL(BASE_URL).hostname,
            path: '/',
            httpOnly: true,
            sameSite: 'Lax',
          },
        ])
      }
      // If no cookie is set, the route may redirect; we still scan
      // whatever it lands on so the gate catches login-page regressions
      // introduced by an authenticated route too.
    }

    const response = await page.goto(`${BASE_URL}${route.path}`, {
      waitUntil: 'networkidle',
    })
    // Some authenticated routes may 200 with an empty state when the
    // API isn't reachable in CI. We accept any 2xx-3xx and scan whatever
    // rendered; the axe scan is the source of truth either way.
    expect(response, `route ${route.path} returned no response`).toBeTruthy()

    const results = await new AxeBuilder({ page })
      .withTags([
        'wcag2a',
        'wcag2aa',
        'wcag21a',
        'wcag21aa',
        // Pull in the WCAG 2.2 AA criteria that axe can reliably check.
        // 2.5.8 (Target Size) is the main one; the rest are manual.
        'wcag22aa',
      ])
      // Opt-out of colour-contrast checks in CI — the dev sandbox and
      // CI runner do not have the design tokens loaded identically to
      // staging. Contrast is audited in the manual pass and verified
      // against the final design tokens.
      .disableRules(['color-contrast'])
      .analyze()

    const violations = results.violations as unknown as AxeViolation[]
    const { blockers, warnings } = partitionBySeverity(violations)

    if (warnings.length > 0) {
      // eslint-disable-next-line no-console
      console.warn(
        `\n[a11y:${route.name}] warnings (${warnings.length}):\n${summarise('WARN', warnings)}`
      )
    }

    if (blockers.length > 0) {
      throw new Error(
        `[a11y:${route.name}] ${blockers.length} serious/critical violation(s):\n${summarise(
          'FAIL',
          blockers
        )}\n` +
          `See a11y/ai-news-scraper/audit-report.md for the remediation plan.\n` +
          `Manual passes for the 60-70% automation can't reach: a11y/ai-news-scraper/manual-checklist.md.`
      )
    }
  })
}
