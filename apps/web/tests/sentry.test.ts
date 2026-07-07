/**
 * Tests for the §16.4 PII redaction contract on the browser SDK side.
 * Runs under vitest (see apps/web/vitest.config.ts).
 *
 * Mirrors the server-side test cases in apps/api/tests/test_sentry_init.py
 * (defined in §16.10). The tests import `beforeSend` and the
 * `redactQueryString` helper directly so the suite does NOT depend
 * on `@sentry/nextjs` being importable at test time (§16.9 graceful
 * degrade).
 *
 * MAJ-1 parity: browser `beforeSend` REPLACES (not drops) event.message
 *   on credential substring. Server-side `_scrub_dict` already
 *   replaces; this suite mirrors that contract.
 * MAJ-2: `event.user.{email, ip_address}` are dropped; `event.user.id`
 *   is replaced with REDACTED.
 * MAJ-6: `beforeSend` does NOT mutate the input event object.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import {
  beforeSend,
  redactQueryString,
  REDACTED,
  type SentryEvent,
  type SentryEventHint,
} from '../sentry.config'

// The test fixtures use untyped object literals; cast once at the
// boundary so the helper's structural `SentryEvent` / `SentryEventHint`
// types unify cleanly. The runtime contract matches what @sentry/nextjs
// actually passes.
const scrub = (event: object, hint: object = {}): SentryEvent | null =>
  beforeSend(event as SentryEvent, hint as SentryEventHint)

describe('Sentry web config — §16.4 PII scrubbing', () => {
  beforeEach(() => {
    // No setup needed: beforeSend is a pure function.
  })

  it('drops events with an Authorization header', () => {
    const event = {
      message: 'something failed',
      request: { headers: { Authorization: 'Bearer xyz' } },
    }
    expect(scrub(event)).toBeNull()
  })

  it('matches Authorization header case-insensitively', () => {
    const event = {
      message: 'something failed',
      request: { headers: { authorization: 'Bearer xyz' } },
    }
    expect(scrub(event)).toBeNull()
  })

  it('drops events with a Cookie header', () => {
    const event = {
      message: 'something failed',
      request: { headers: { Cookie: 'session=abc' } },
    }
    expect(scrub(event)).toBeNull()
  })

  it('drops events with a Set-Cookie header', () => {
    const event = {
      message: 'something failed',
      request: { headers: { 'Set-Cookie': 'session=abc; HttpOnly' } },
    }
    expect(scrub(event)).toBeNull()
  })

  it('drops events when request.cookies dict is non-empty', () => {
    const event = {
      message: 'something failed',
      request: { cookies: { session: 'abc' } },
    }
    expect(scrub(event)).toBeNull()
  })

  it('redacts password query param but preserves the key', () => {
    const event = {
      message: 'something failed',
      request: { query_string: 'password=hunter2&page=1' },
    }
    const result = scrub(event)
    expect(result).not.toBeNull()
    const qs = String(result?.request?.query_string ?? '')
    expect(qs).toContain('password=' + encodeURIComponent('[REDACTED]'))
    expect(qs).toContain('page=1')
    expect(qs).not.toContain('hunter2')
  })

  it('redacts token / jwt / secret query params case-insensitively', () => {
    const cases = ['token=abc', 'Token=abc', 'jwt=eyJabc', 'SECRET=topsecret']
    for (const qs of cases) {
      const event = { message: 'x', request: { query_string: qs } }
      const result = scrub(event)
      expect(result, `case: ${qs}`).not.toBeNull()
      const out = String(result?.request?.query_string ?? '')
      expect(out, `case: ${qs}`).not.toMatch(/(abc|eyJabc|topsecret)/)
    }
  })

  // ---- MAJ-1: REPLACE (not drop) on credential substring ----

  it('REPLACES event.message with REDACTED on JWT-shape substring', () => {
    const event = {
      message: 'bearer eyJhbGciOiJIUzI1NiJ9.payload.signature',
    }
    const result = scrub(event)
    expect(result).not.toBeNull()
    expect(result?.message).toBe(REDACTED)
    // The original message is gone — the credential substring is masked.
    expect(result?.message).not.toContain('eyJ')
  })

  it('REPLACES event.message with REDACTED on "Bearer "', () => {
    const event = { message: 'rejected Bearer token' }
    const result = scrub(event)
    expect(result).not.toBeNull()
    expect(result?.message).toBe(REDACTED)
    expect(result?.message).not.toContain('Bearer')
  })

  it('REPLACES event.message with REDACTED on "JWT "', () => {
    const event = { message: 'JWT validation failed' }
    const result = scrub(event)
    expect(result).not.toBeNull()
    expect(result?.message).toBe(REDACTED)
    expect(result?.message).not.toContain('JWT')
  })

  it('passes through events with no sensitive payload', () => {
    const event = {
      message: 'plain error',
      request: { headers: { 'X-Request-ID': 'req-123' } },
    }
    const result = scrub(event)
    expect(result).not.toBeNull()
    expect(result?.message).toBe('plain error')
  })

  it('handles array-form query_string (some SDKs emit tuples)', () => {
    const event = {
      message: 'x',
      request: { query_string: ['password=hunter2', 'page=1'] },
    }
    const result = scrub(event)
    expect(result).not.toBeNull()
    const qs = String(result?.request?.query_string ?? '')
    expect(qs).toContain('password=' + encodeURIComponent('[REDACTED]'))
    expect(qs).toContain('page=1')
  })

  // ---- MAJ-2: event.user PII scrubbing ----

  it('drops event.user.email but preserves other user fields', () => {
    const event = {
      message: 'auth failed',
      user: { id: 'user-123', email: 'alice@example.com', username: 'alice' },
    }
    const result = scrub(event)
    expect(result).not.toBeNull()
    const user = result?.user as Record<string, unknown> | undefined
    expect(user).toBeDefined()
    expect('email' in (user ?? {})).toBe(false)
    expect(user?.['username']).toBe('alice')
    // id is REPLACED with REDACTED (cardinality preserved).
    expect(user?.['id']).toBe(REDACTED)
  })

  it('drops event.user.ip_address', () => {
    const event = {
      message: 'request',
      user: { id: 'user-123', ip_address: '192.168.1.1' },
    }
    const result = scrub(event)
    expect(result).not.toBeNull()
    const user = result?.user as Record<string, unknown> | undefined
    expect(user).toBeDefined()
    expect('ip_address' in (user ?? {})).toBe(false)
  })

  it('preserves non-PII user fields (username, segment)', () => {
    const event = {
      message: 'request',
      user: {
        id: 'user-123',
        email: 'alice@example.com',
        username: 'alice',
        segment: 'beta',
      },
    }
    const result = scrub(event)
    expect(result).not.toBeNull()
    const user = result?.user as Record<string, unknown> | undefined
    expect(user?.['username']).toBe('alice')
    expect(user?.['segment']).toBe('beta')
    expect('email' in (user ?? {})).toBe(false)
  })

  it('passes events with no event.user through unchanged', () => {
    const event = { message: 'plain error' }
    const result = scrub(event)
    expect(result).not.toBeNull()
    expect(result?.user).toBeUndefined()
  })

  // ---- MAJ-6: input event is NOT mutated ----

  it('does not mutate the input event on query_string redaction', () => {
    const event = {
      message: 'something failed',
      request: { query_string: 'password=hunter2&page=1' },
    }
    const originalQs = event.request!.query_string
    scrub(event)
    // Input must be untouched. If beforeSend mutated in place,
    // this assertion fails.
    expect(event.request!.query_string).toBe(originalQs)
    expect(event.request!.query_string).toBe('password=hunter2&page=1')
  })

  it('does not mutate the input event on credential message redact', () => {
    const event = { message: 'rejected Bearer token' }
    const originalMessage = event.message
    scrub(event)
    expect(event.message).toBe(originalMessage)
    expect(event.message).toBe('rejected Bearer token')
  })

  it('does not mutate the input event on user PII scrub', () => {
    const event = {
      message: 'auth',
      user: { id: 'user-123', email: 'alice@example.com' },
    }
    const originalUser = { ...event.user }
    scrub(event)
    expect(event.user).toEqual(originalUser)
    expect(event.user!.email).toBe('alice@example.com')
    expect(event.user!.id).toBe('user-123')
  })
})

describe('Sentry web config — redactQueryString helper', () => {
  it('returns an empty string untouched', () => {
    expect(redactQueryString('')).toBe('')
  })

  it('preserves non-sensitive params unchanged', () => {
    expect(redactQueryString('page=2&sort=asc')).toBe('page=2&sort=asc')
  })

  it('redacts multiple sensitive keys in the same string', () => {
    const out = redactQueryString('password=alpha&token=beta&page=1')
    expect(out).toContain('password=' + encodeURIComponent('[REDACTED]'))
    expect(out).toContain('token=' + encodeURIComponent('[REDACTED]'))
    expect(out).toContain('page=1')
    // Original values are dropped entirely; keys + REDACTED remain.
    expect(out).not.toContain('alpha')
    expect(out).not.toContain('beta')
  })
})
