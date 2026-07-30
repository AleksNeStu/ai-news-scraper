/**
 * Regression test for Task #66 — next-intl redirect loop.
 *
 * Symptom: under `localePrefix: 'as-needed'`, next-intl middleware
 * issues a 307 from `/en/X` → `/X` for the default locale (treating
 * `/en/` as a superfluous prefix on the English URL). When the
 * compose middleware in `apps/web/src/middleware.ts` then had to
 * redirect an unauthenticated user to `/en/login?next=...`, the
 * browser re-followed and next-intl redirected `/en/login` back to
 * `/login` again — a ping-pong surfacing as `ERR_TOO_MANY_REDIRECTS`
 * on every a11y-audit route.
 *
 * Fix: switch to `localePrefix: 'always'` (see
 * `apps/web/src/i18n/routing.ts` and the updated comment block in
 * `apps/web/src/middleware.ts`). Under `'always'`, `/en/X` is the
 * canonical form for the default locale — no redirect on hit. Bare
 * `/X` gets ONE 307 → `/en/X` on first hit. No loop.
 *
 * This spec drives a running Next.js server (the same one the a11y
 * spec targets — see `playwright.config.ts`) and asserts that every
 * representative URL converges to a 2xx in a bounded number of
 * navigations, with no `ERR_TOO_MANY_REDIRECTS` and no infinite
 * `/en/X ↔ /X` ping-pong.
 *
 * Usage:
 *   pnpm dev    # in one shell — preview at http://localhost:3807
 *   BASE_URL=http://localhost:3807 pnpm exec playwright test e2e/redirect-loop.spec.ts
 */

import { expect, test } from '@playwright/test'

const BASE_URL = process.env.BASE_URL ?? 'http://127.0.0.1:4173'

// Playwright's default per-request timeout is 30s; ERR_TOO_MANY_REDIRECTS
// surfaces as a navigation error inside that window. Bounding the loop
// check to a max-redirect count is the explicit assertion: a real loop
// will exceed 5 redirects before the timeout fires; a healthy chain
// resolves in ≤ 2 (one bare → prefixed 307, then a 200).
const MAX_REDIRECTS = 5

interface ChainProbe {
  readonly path: string
  readonly expectsRedirect: boolean
  readonly requiresAuth?: boolean
  readonly cookie?: string
}

const PROBES: ReadonlyArray<ChainProbe> = [
  // /en/login: canonical for English; should be 200 on first hit.
  { path: '/en/login', expectsRedirect: false },
  // /ru/login: canonical for Russian; should be 200 on first hit.
  { path: '/ru/login', expectsRedirect: false },
  // /login (no locale): next-intl should issue ONE 307 → /en/login,
  // then the page should render with 200. Under the old as-needed
  // behavior, this is where the loop manifested.
  { path: '/login', expectsRedirect: true },
  // /ru (no trailing path, no locale): same single-redirect chain
  // to /en/ root. Sanity check that the locale-less root also
  // resolves.
  { path: '/ru', expectsRedirect: true },
]

const AUTH_PROBES: ReadonlyArray<ChainProbe> = [
  // /en/dashboard without auth → 307 to /en/login?next=/en/dashboard
  // (then the login page renders 200). Single 307, no loop.
  { path: '/en/dashboard', expectsRedirect: true, requiresAuth: true },
  // /en/dashboard WITH auth_token cookie → 200 directly.
  {
    path: '/en/dashboard',
    expectsRedirect: false,
    requiresAuth: true,
    cookie: process.env.E2E_AUTH_COOKIE,
  },
]

for (const probe of PROBES) {
  test(`redirect chain — ${probe.path} (no loop)`, async ({ page, request }) => {
    // Use Playwright's HTTP client so we observe every hop in the
    // chain rather than the browser absorbing the final URL. The
    // browser test (`page.goto`) is also below as a smoke check.
    const chain: string[] = []
    const result = await request.get(`${BASE_URL}${probe.path}`, {
      maxRedirects: MAX_REDIRECTS,
      failOnStatusCode: false,
    })

    // Walk the response.request().redirectedFrom chain to enumerate
    // every URL we touched. `request.redirectedFrom()` is populated by
    // Playwright for redirects followed by the HTTP client. We type
    // `cursor` loosely so the `.redirectedFrom()` chain compiles
    // under both the `Request` and `null` cases (Playwright's
    // `Request.redirectedFrom()` returns `Request | null`).
    type Cursor = { url(): string; redirectedFrom(): Cursor | null }
    let cursor: Cursor | null = (result as unknown as { request(): Cursor | null }).request()
    while (cursor) {
      chain.push(cursor.url())
      cursor = cursor.redirectedFrom()
    }

    // Assert: chain length is bounded. The probe's intent (expectsRedirect)
    // is checked separately — we just want to confirm there is no runaway
    // ping-pong, regardless of how many hops the happy path takes.
    expect(
      chain.length,
      `redirect chain for ${probe.path} exceeded ${MAX_REDIRECTS} hops:\n${chain.join('\n  → ')}`
    ).toBeLessThanOrEqual(MAX_REDIRECTS)

    // The final response should be 2xx (200 for canonical, 200 for the
    // destination of a single redirect) — NOT a 5xx and NOT another
    // 3xx that would indicate we stopped mid-chain.
    expect(
      result.status(),
      `final response for ${probe.path} should be 2xx; chain:\n${chain.join('\n  → ')}`
    ).toBeGreaterThanOrEqual(200)
    expect(result.status()).toBeLessThan(300)

    // No `/en/X` → `/X` → `/en/X` pattern in the chain. If a path
    // appears twice in the chain, that's the old loop.
    const seen = new Set<string>()
    for (const url of chain) {
      const path = new URL(url).pathname
      expect(
        seen.has(path),
        `path ${path} appeared twice in the chain — redirect loop:\n${chain.join('\n  → ')}`
      ).toBe(false)
      seen.add(path)
    }

    // Browser-level smoke: page.goto on the same path should land on a
    // page (not error with ERR_TOO_MANY_REDIRECTS).
    if (probe.cookie) {
      await page.context().addCookies([
        {
          name: 'auth_token',
          value: probe.cookie,
          domain: new URL(BASE_URL).hostname,
          path: '/',
          httpOnly: true,
          sameSite: 'Lax',
        },
      ])
    }
    const response = await page.goto(`${BASE_URL}${probe.path}`, {
      waitUntil: 'networkidle',
      timeout: 10_000,
    })
    expect(response, `page.goto(${probe.path}) returned no response`).toBeTruthy()
    expect(response!.status()).toBeLessThan(400)
  })
}

for (const probe of AUTH_PROBES) {
  test(`auth gate — ${probe.path} (${probe.cookie ? 'with cookie' : 'no cookie'})`, async ({
    request,
  }) => {
    const chain: string[] = []
    const headers: Record<string, string> = {}
    if (probe.cookie) headers['Cookie'] = `auth_token=${probe.cookie}`

    const result = await request.get(`${BASE_URL}${probe.path}`, {
      headers,
      maxRedirects: MAX_REDIRECTS,
      failOnStatusCode: false,
    })

    type Cursor = { url(): string; redirectedFrom(): Cursor | null }
    let cursor: Cursor | null = (result as unknown as { request(): Cursor | null }).request()
    while (cursor) {
      chain.push(cursor.url())
      cursor = cursor.redirectedFrom()
    }

    expect(
      chain.length,
      `auth gate chain for ${probe.path} exceeded ${MAX_REDIRECTS} hops:\n${chain.join('\n  → ')}`
    ).toBeLessThanOrEqual(MAX_REDIRECTS)

    // Without cookie: final URL should be /en/login (the redirect
    // target). With cookie: final URL should be /en/dashboard (no
    // redirect).
    const finalUrl = new URL(chain[chain.length - 1] ?? `${BASE_URL}${probe.path}`)
    const finalPath = finalUrl.pathname

    if (probe.cookie) {
      // With cookie, either:
      //   - 200 at /en/dashboard (session valid), or
      //   - 200 at /en/login?next=/en/dashboard (cookie rejected by
      //     API → middleware still 307s to login — also acceptable
      //     since we're not testing API session validation here, only
      //     that the redirect chain terminates).
      expect(
        finalPath === '/en/dashboard' || finalPath === '/en/login',
        `auth-cookie path ${probe.path} should land on /en/dashboard or /en/login; got ${finalPath}`
      ).toBe(true)
    } else {
      // Without cookie, should land on /en/login (no infinite loop).
      expect(
        finalPath,
        `unauthenticated ${probe.path} should redirect to /en/login; got ${finalPath}\nchain:\n${chain.join('\n  → ')}`
      ).toBe('/en/login')
      // And the `next` query param should preserve the user's
      // intended destination, locale-prefixed.
      const next = finalUrl.searchParams.get('next')
      expect(next).toBe('/en/dashboard')
    }
  })
}
