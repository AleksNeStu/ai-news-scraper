'use client'

/**
 * Global error boundary — rendered OUTSIDE the app's root layout
 * when an unhandled exception escapes the segment-level error.tsx /
 * not-found.tsx / error boundary chain.
 *
 * In Next.js 15 with `output: 'standalone'`, any unhandled error
 * during render wraps the failed page in this `<html id="__next_error__">`
 * shell. Without `<html lang>` on the wrapper, axe-core (the a11y
 * CI gate) flags every route as [serious] `html-has-lang` — even
 * when the underlying page IS a properly-localised route. CI then
 * fails the whole a11y-pr job on a single missing attribute on
 * the framework's error shell.
 *
 * The fix per Next.js 15 docs: a `global-error.tsx` MUST render
 * its own `<html lang>` and `<body>`. It REPLACES the default
 * error shell. Default lang is `en` (the project's default
 * locale) — for a localised error shell, derive from the path
 * (the URL is available via `window.location` after hydration).
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
          background: '#0b0b0c',
          color: '#fafafa',
        }}
      >
        <main
          style={{
            maxWidth: 560,
            margin: '0 auto',
            padding: '6rem 1.5rem',
            textAlign: 'center',
          }}
        >
          <h1 style={{ fontSize: 32, margin: 0, fontWeight: 600 }}>Something went wrong</h1>
          <p
            style={{
              marginTop: 12,
              fontSize: 14,
              color: '#a1a1aa',
              lineHeight: 1.5,
            }}
          >
            An unexpected error occurred. You can retry, or head back to the home page.
          </p>
          {error.digest ? (
            <p
              style={{
                marginTop: 16,
                fontSize: 12,
                color: '#71717a',
                fontFamily: 'monospace',
              }}
              aria-label="Error digest"
            >
              digest: {error.digest}
            </p>
          ) : null}
          <div
            style={{
              display: 'flex',
              gap: 8,
              justifyContent: 'center',
              marginTop: 32,
            }}
          >
            <button
              type="button"
              onClick={reset}
              style={{
                cursor: 'pointer',
                border: '1px solid #3f3f46',
                background: 'transparent',
                color: '#fafafa',
                padding: '8px 16px',
                borderRadius: 6,
                fontSize: 14,
              }}
            >
              Try again
            </button>
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a
              href="/en"
              style={{
                border: '1px solid #fafafa',
                background: '#fafafa',
                color: '#0b0b0c',
                padding: '8px 16px',
                borderRadius: 6,
                fontSize: 14,
                textDecoration: 'none',
              }}
            >
              Back to home
            </a>
          </div>
        </main>
      </body>
    </html>
  )
}
