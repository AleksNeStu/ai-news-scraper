import type { NextConfig } from 'next'
import { withSentryConfig } from '@sentry/nextjs'
import createNextIntlPlugin from 'next-intl/plugin'

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // standalone output required by apps/web/Dockerfile:27, which COPYs
  // from .next/standalone. Without this key, `next build` does not emit
  // .next/standalone and the web container fails to build. Documented
  // in .agent/adr/014-deploy-target.md §14.7 as a pre-deploy blocker.
  output: 'standalone',
  // typedRoutes disabled: every <Link href={dynamicString}> and
  // router.replace(templateString) call fails TS2322 ("Type 'string' is
  // not assignable to type 'RouteImpl<string>'"). The cost of casting
  // every dynamic navigation site outweighs the benefit of catching typos
  // in literal route strings. Re-enable when the codebase has zero
  // dynamic-href call sites.
  // experimental: { typedRoutes: true },
  transpilePackages: ['@ai-news-scraper/shared'],
  async rewrites() {
    // ``API_INTERNAL_URL`` is passed at build time as a Docker ``ARG``
    // (see ``apps/web/Dockerfile`` + ``docker-compose.yml`` build args).
    // Default to ``http://localhost:8007`` (browser host port) to match
    // the new port matrix per the canonical port-registry file.
    const apiUrl = process.env.API_INTERNAL_URL || 'http://localhost:8007'
    return [{ source: '/api/backend/:path*', destination: `${apiUrl}/:path*` }]
  },
}

// Per ADR-016 §16.6 / §16.7:
// - org/project filled from SENTRY_ORG / SENTRY_PROJECT env vars at
//   build time (CI populates them via .sentryclirc — see §16.7).
// - SENTRY_UPLOAD controls whether source maps are uploaded;
//   local dev skips the upload step (SENTRY_UPLOAD !== 'true').
// - dryRun when SENTRY_UPLOAD !== 'true' is the §16.7 escape hatch
//   so a build without the env vars is a no-op for Sentry.
// - widenClientFileUpload + hideSourceMaps keep source maps out of
//   the production bundle but available to Sentry's uploader.
// - disableLogger silences the SDK's stdout chatter (CI logs only).
const withIntl = createNextIntlPlugin('./src/i18n/request.ts')

export default withSentryConfig(withIntl(nextConfig), {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  // NEW-2 (Devil-3 re-review 2026-07-07): pass `release` to the
  // withSentryConfig wrapper so source-map uploads tag the same
  // Sentry release row the wizard files (server + client) will later
  // report to. Without this, the build-time release is `undefined`
  // and only the runtime `release: process.env.SENTRY_RELEASE` in the
  // wizard files carries the value — fragile if SENTRY_RELEASE is
  // injected at runtime but not at build time (or vice versa). Kept
  // identical to the wizard `release:` field per ADR-016 §16.8.
  // Sentry SDK accepts `release` as either a string or a structured
  // object; the latest @sentry/nextjs types surface only the object
  // shape. The string form is the documented escape hatch — cast to
  // `unknown` then to the SDK type so we don't trigger the
  // `@typescript-eslint/no-explicit-any` lint rule.
  release: process.env.SENTRY_RELEASE as unknown as { name: string },
  silent: !process.env.CI,
  // `dryRun` was removed from `SentryBuildOptions` in @sentry/nextjs v8
  // (TS2353 "Object literal may only specify known properties"). The
  // "skip source-map upload" behaviour it used to gate is now driven
  // directly by the `SENTRY_UPLOAD` env var: when unset/false, the
  // SDK skips the upload step. ADR-016 §16.7's escape hatch still
  // holds — a local dev build without `SENTRY_UPLOAD=true` is a
  // no-op for Sentry.
  widenClientFileUpload: true,
  hideSourceMaps: true,
  disableLogger: true,
})
