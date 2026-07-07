/**
 * Sentry browser-side init — discovered by @sentry/nextjs >=8 at
 * module load time on the browser runtime. Pairs with
 * `sentry.server.config.ts` for the server runtime; both call the
 * shared `beforeSend` helper from `./sentry.config`.
 *
 * Per ADR-016 §16.6 / MAJ-4: the SDK requires this filename
 * specifically to fire init on the browser; a single
 * `sentry.config.ts` is NOT picked up on both runtimes.
 */

import * as Sentry from '@sentry/nextjs'
import type { BrowserOptions } from '@sentry/nextjs'
import {
  beforeSend,
  DENY_URL_PATTERNS,
  resolveEnvironment,
  type SentryEvent,
  type SentryEventHint,
} from './sentry.config'

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN

// Cast at the call-site boundary: `Sentry.init` accepts a structural
// BrowserOptions['beforeSend'] whose types don't unify cleanly with our
// structural `SentryEvent` interface (the SDK's `Event` union has a
// `transaction` type-variant that doesn't fit the browser-side
// `ErrorEvent` slot). The runtime contract is identical to the
// server-side hook.
const beforeSendAdapter = (event: unknown, hint: unknown): unknown =>
  beforeSend(event as SentryEvent, hint as SentryEventHint)

if (SENTRY_DSN) {
  try {
    Sentry.init({
      dsn: SENTRY_DSN,
      tracesSampleRate: 0.2,
      replaysSessionSampleRate: 0.1,
      replaysOnErrorSampleRate: 1.0,
      sendDefaultPii: false,
      release: process.env.SENTRY_RELEASE,
      environment: resolveEnvironment(),
      denyUrls: DENY_URL_PATTERNS,
      beforeSend: beforeSendAdapter as unknown as BrowserOptions['beforeSend'],
    })
  } catch (err) {
    // §16.9 — observability must never become a startup dependency.
    // NIT-3 — log so the operator sees init failures in the browser
    // console (the previous silent catch swallowed bad DSNs and
    // network-unreachable errors without any signal).
    console.warn('[sentry] client init failed:', err)
  }
}
