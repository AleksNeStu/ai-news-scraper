/**
 * Sentry server-side init — discovered by @sentry/nextjs >=8 at
 * module load time on the server runtime. Pairs with
 * `sentry.client.config.ts` for the browser runtime; both call the
 * shared `beforeSend` helper from `./sentry.config`.
 *
 * Per ADR-016 §16.6 / MAJ-4: the SDK requires this filename
 * specifically to fire init on the server runtime. Without it,
 * Server Component errors and route-handler exceptions are NEVER
 * captured (the SDK looks at runtime-specific filenames to pick
 * which init file to run).
 *
 * NOTE: the server runtime does NOT receive `denyUrls` — that field
 * filters browser fetches, which are a browser-side concept. The
 * PII contract for the server runtime is enforced inside `beforeSend`
 * (same helper, identical rules).
 */

import * as Sentry from '@sentry/nextjs'
import type { NodeOptions } from '@sentry/nextjs'
import {
  beforeSend,
  resolveEnvironment,
  type SentryEvent,
  type SentryEventHint,
} from './sentry.config'

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN

// Cast at the call-site boundary for the same reason as the client
// wizard file: the SDK's NodeOptions['beforeSend'] signature uses the
// full Event union, while our structural helper captures only the
// fields we touch. The runtime contract is identical.
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
      beforeSend: beforeSendAdapter as unknown as NodeOptions['beforeSend'],
    })
  } catch (err) {
    // §16.9 — observability must never become a startup dependency.
    // NIT-3 — log so the operator sees init failures (the previous
    // silent catch swallowed bad DSNs and network-unreachable
    // errors without any signal).
    console.warn('[sentry] server init failed:', err)
  }
}
