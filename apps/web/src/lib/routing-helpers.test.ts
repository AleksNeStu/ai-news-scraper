/**
 * Unit tests for the locale-prefix helpers extracted from
 * ``apps/web/src/middleware.ts`` (Task #66).
 *
 * Why these are tested directly:
 *   The pre-Task #66 ``withLocalePrefix`` had a short-circuit for the
 *   default locale that returned bare paths (`/login` instead of
 *   `/en/login`). That short-circuit is what caused the a11y CI gate's
 *   ``ERR_TOO_MANY_REDIRECTS`` loop — when the compose middleware
 *   built the redirect target for an unauthenticated user, it emitted
 *   the bare ``/login``, and the next request through ``next-intl``'s
 *   middleware bounced ``/en/login`` back to ``/login`` again.
 *
 *   These tests pin down the post-Task #66 contract:
 *     - ``stripLocalePrefix`` strips any leading locale segment.
 *     - ``withLocalePrefix`` ALWAYS emits ``/<locale>...`` — even for
 *       the default locale. There is no bare-path code path.
 *
 * Runs under vitest (see ``apps/web/vitest.config.ts``).
 */

import { describe, it, expect } from 'vitest'
import { stripLocalePrefix, withLocalePrefix } from './routing-helpers'

describe('stripLocalePrefix', () => {
  it('strips /en/ from a deep path', () => {
    expect(stripLocalePrefix('/en/dashboard')).toBe('/dashboard')
  })

  it('strips /ru/ from a deep path', () => {
    expect(stripLocalePrefix('/ru/login')).toBe('/login')
  })

  it('maps /en to / (root)', () => {
    expect(stripLocalePrefix('/en')).toBe('/')
  })

  it('maps /ru to / (root)', () => {
    expect(stripLocalePrefix('/ru')).toBe('/')
  })

  it('preserves a bare path unchanged (defensive fallback)', () => {
    expect(stripLocalePrefix('/dashboard')).toBe('/dashboard')
  })

  it('preserves nested paths with the locale stripped', () => {
    expect(stripLocalePrefix('/en/articles/123')).toBe('/articles/123')
    expect(stripLocalePrefix('/ru/dashboard/brief/2026-01-15')).toBe('/dashboard/brief/2026-01-15')
  })
})

describe('withLocalePrefix', () => {
  it('prefixes a canonical path for the default locale', () => {
    // CRITICAL: post-Task #66, the default locale MUST still get the
    // /en prefix. The pre-fix short-circuit that returned bare paths
    // was the source of the redirect loop.
    expect(withLocalePrefix('/login', 'en')).toBe('/en/login')
  })

  it('prefixes a canonical path for a non-default locale', () => {
    expect(withLocalePrefix('/login', 'ru')).toBe('/ru/login')
  })

  it('prefixes the root path for the default locale', () => {
    expect(withLocalePrefix('/', 'en')).toBe('/en')
  })

  it('prefixes the root path for a non-default locale', () => {
    expect(withLocalePrefix('/', 'ru')).toBe('/ru')
  })

  it('prefixes a nested canonical path', () => {
    expect(withLocalePrefix('/dashboard/brief/2026-01-15', 'en')).toBe(
      '/en/dashboard/brief/2026-01-15'
    )
    expect(withLocalePrefix('/articles/123', 'ru')).toBe('/ru/articles/123')
  })

  it('NEVER returns a bare path for any locale (regression — Task #66)', () => {
    // This is the explicit regression pin: under the old as-needed
    // behavior, withLocalePrefix('/login', 'en') returned '/login',
    // which the compose middleware then turned into a 307 target —
    // and next-intl's middleware would redirect /en/login back to
    // /login, forming the loop. The fix is to ALWAYS prefix.
    for (const locale of ['en', 'ru']) {
      const out = withLocalePrefix('/login', locale)
      expect(out, `${locale} must produce a prefixed URL`).toMatch(/^\/(en|ru)\//)
    }
  })
})
