/**
 * Sentry web config — pure helpers shared between client and server
 * runtimes.
 *
 * Implements ADR-016 §16.4 (PII scrubbing) and §16.6 (web-side
 * Sentry wiring). The two wizard files
 * (`sentry.client.config.ts` and `sentry.server.config.ts`) call
 * `Sentry.init({ ..., beforeSend })`. This module exports ONLY the
 * SDK-agnostic helpers; it does NOT initialise the SDK itself
 * (per MAJ-4 — @sentry/nextjs >=8 requires the two wizard entry
 * points to fire init on each runtime).
 *
 * The `beforeSend` hook is the SDK-level layer of the §16.4 PII
 * contract: it drops events whose request carries an Authorization
 * or Cookie header, whose cookies dict is non-empty, and whose
 * extra/contexts carry sensitive keys; it redacts sensitive
 * query-string keys (password, token, etc.) keeping the key but
 * replacing the value with "[REDACTED]"; it REDACTS (not drops)
 * credential-bearing messages so legitimate errors that happen to
 * mention "Bearer" still surface (§16.4(a) parity with the server
 * `_scrub_dict` helper); it scrubs `event.user` PII
 * (email/ip_address dropped, id replaced with the sentinel).
 *
 * Both halves of a deploy (api + web) MUST report the same
 * SENTRY_RELEASE so a Python traceback and a browser error from the
 * same commit land under one Sentry release row (§16.8).
 *
 * TYPE NOTE: `@sentry/nextjs`'s browser `beforeSend` types its
 * argument as `ErrorEvent` (the more restrictive `type: undefined`
 * variant), while the server runtime types it as the full `Event`
 * union. The helper below is typed against a structural `SentryEvent`
 * interface that captures ONLY the fields we read or write, so the
 * same callable satisfies both `BrowserOptions['beforeSend']` and
 * `NodeOptions['beforeSend']`. The wizard files pass it directly.
 */

// ---------- types ----------

/**
 * Structural subset of the Sentry event payload we touch. Defined as a
 * plain interface (not `Sentry.Event`) so the same function satisfies
 * both the browser `ErrorEvent` signature and the server `Event`
 * signature without a generic parameter on every call site.
 */
export interface SentryEvent {
  message?: string
  request?: {
    headers?: Record<string, unknown>
    cookies?: Record<string, unknown>
    query_string?: string | string[] | [string, string][]
    url?: string
    [key: string]: unknown
  }
  user?: {
    id?: string | number
    email?: string
    ip_address?: string
    username?: string
    [key: string]: unknown
  }
  extra?: Record<string, unknown>
  contexts?: Record<string, unknown>
  breadcrumbs?: { values?: Array<Record<string, unknown>> }
  [key: string]: unknown
}

/** `EventHint` from `@sentry/nextjs`; structural subset for type compat. */
export interface SentryEventHint {
  [key: string]: unknown
}

/** Token printed in place of any redacted value. */
export const REDACTED = '[REDACTED]'

/**
 * Query-string keys whose value MUST be redacted (case-insensitive).
 * Mirrors the server-side contract in apps/api/api/sentry_init.py.
 */
export const SENSITIVE_QUERY_KEYS = new Set<string>([
  'password',
  'pass',
  'pwd',
  'passwd',
  'token',
  'jwt',
  'key',
  'secret',
])

/** Redact sensitive keys in a `key=value&key=value` query string. */
export function redactQueryString(qs: string): string {
  if (!qs) return qs
  return qs
    .split('&')
    .map((pair) => {
      const eqIdx = pair.indexOf('=')
      const key = eqIdx >= 0 ? pair.slice(0, eqIdx) : pair
      if (SENSITIVE_QUERY_KEYS.has(key.toLowerCase())) {
        // Value is intentionally replaced with REDACTED; never
        // read the original. The key stays so the operator still
        // sees which query param was sent.
        return `${key}=${encodeURIComponent(REDACTED)}`
      }
      return pair
    })
    .join('&')
}

/**
 * Normalize event.request.query_string to a single string, whatever
 * shape the SDK feeds us (string | string[] | [k,v][]).
 */
function queryStringToString(qs: string | string[] | [string, string][] | undefined): string {
  if (!qs) return ''
  if (Array.isArray(qs)) {
    if (qs.length === 0) return ''
    // [k,v] tuple shape → re-encode as key=value
    if (Array.isArray(qs[0])) {
      return (qs as [string, string][]).map(([k, v]) => `${k}=${v}`).join('&')
    }
    return qs.join('&')
  }
  return String(qs)
}

/**
 * §16.4(a) PII drop + redact hook. Returns a NEW event object (does
 * not mutate the input) — see MAJ-6. The SDK may pass a frozen
 * event object across minor upgrades; spreading first protects the
 * redaction from silently no-op'ing.
 *
 * Drops (return null) on:
 *  - Authorization / Cookie / Set-Cookie request header
 *  - non-empty request.cookies dict
 *
 * Redacts (keeps event, returns scrubbed copy) on:
 *  - sensitive query-string keys (password, token, etc.)
 *  - credential substring in event.message (Bearer / JWT / eyJ...) —
 *    replaced with REDACTED, NOT dropped (parity with the server
 *    `_scrub_dict` helper, per MAJ-1)
 *  - event.user.email / event.user.ip_address dropped;
 *    event.user.id replaced with REDACTED (MAJ-2)
 */
export function beforeSend(event: SentryEvent, _hint: SentryEventHint): SentryEvent | null {
  // Drop on any auth/cookie header (case-insensitive)
  const headers = event.request?.headers ?? {}
  const lower: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(headers)) {
    lower[k.toLowerCase()] = v
  }
  if (lower['authorization'] || lower['cookie'] || lower['set-cookie']) {
    return null
  }

  // Drop on cookies dict
  if (event.request?.cookies && Object.keys(event.request.cookies).length > 0) {
    return null
  }

  // Build a new request object if any request-level redaction fires.
  // Do NOT mutate the input — see MAJ-6 / server `_scrub_dict`.
  let request: SentryEvent['request'] | undefined = event.request
  if (event.request?.query_string !== undefined) {
    const qs = queryStringToString(event.request.query_string)
    if (qs) {
      request = {
        ...(event.request ?? {}),
        query_string: redactQueryString(qs),
      }
    }
  }

  // Redact credential substring in event.message — REPLACE, not drop
  // (MAJ-1 parity with server `_scrub_dict`). Legitimate errors that
  // happen to mention "Bearer" / "JWT" still surface; only the value
  // is masked.
  let message: string | undefined = event.message
  const msg = String(message ?? '')
  if (msg.match(/eyJ[A-Za-z0-9_-]{10,}/) || msg.includes('Bearer ') || msg.includes('JWT ')) {
    message = REDACTED
  }

  // Scrub event.user (MAJ-2). Email / ip_address are dropped entirely;
  // id is replaced with the sentinel (preserves cardinality).
  let user: SentryEvent['user'] | undefined = event.user
  if (user) {
    const next: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(user)) {
      const kl = k.toLowerCase()
      if (kl === 'email' || kl === 'ip_address') continue
      if (kl === 'id') next[k] = REDACTED
      else next[k] = v
    }
    user = next as SentryEvent['user']
  }

  // If nothing changed, return the original reference (SDK-friendly).
  if (request === event.request && message === event.message && user === event.user) {
    return event
  }

  const out: SentryEvent = { ...event }
  if (request !== event.request) out.request = request
  if (message !== event.message) out.message = message
  if (user !== event.user) out.user = user
  return out
}

/**
 * Resolve the Sentry environment tag. Priority:
 *   1. NEXT_PUBLIC_APP_ENV  (operator override, documented in .env.example)
 *   2. NODE_ENV             (Next.js hard contract: 'development' in next dev,
 *                            'production' in next start)
 *   3. 'development'        (final fallback — NOT 'production', per MAJ-5)
 *
 * The previous default of 'production' silently tagged every dev event
 * as production. Next.js sets NODE_ENV correctly in every build mode,
 * so step 2 is the safe runtime default.
 */
export function resolveEnvironment(): string {
  return process.env.NEXT_PUBLIC_APP_ENV ?? process.env.NODE_ENV ?? 'development'
}

/**
 * The denyUrls regex list — auth-route paths the SDK should not
 * capture against. Updated from /^\/api\/auth\// to the real route
 * shape used in this project: the browser hits
 * /api/backend/.../auth/... via the Next.js rewrite at
 * `apps/web/next.config.ts:21`, and the page-route layer for
 * /auth/... lives under the same prefix. Both must be excluded
 * (MAJ-3).
 */
export const DENY_URL_PATTERNS: RegExp[] = [/^\/api\/backend\/auth\//, /^\/auth\//]
