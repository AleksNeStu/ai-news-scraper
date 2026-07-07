'use client'

import { useActionState, useEffect, useRef, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Newspaper } from 'lucide-react'
import { Link } from '@/i18n/navigation'
import { loginAction, type LoginState } from '@/lib/auth'

const initialState: LoginState = { ok: false }

/**
 * Login page (Task #32).
 *
 * - Locale propagation: server actions do not auto-receive the active
 *   locale, so we pass `locale` as the third positional arg to
 *   `loginAction`. The action builds a server-side translator via
 *   `createTranslator` and uses it to localize error messages (e.g.
 *   the 429 cooldown error with its ICU plural).
 * - UI strings flow from `useTranslations('Auth.Login')`.
 */
export default function LoginPage() {
  const t = useTranslations('Auth.Login')
  const locale = useLocale()
  const [state, action, pending] = useActionState(
    async (prev: LoginState, formData: FormData) => loginAction(prev, formData, locale),
    initialState
  )
  const [cooldown, setCooldown] = useState(0)
  const errorRef = useRef<HTMLParagraphElement | null>(null)

  // Drive the cooldown countdown. When `state.retryAfter` arrives (a 429
  // happened), seed the countdown; tick it down once per second until it
  // hits 0; only then can the user submit again.
  useEffect(() => {
    if (state.code === 'rate_limited' && state.retryAfter) {
      setCooldown(state.retryAfter)
    }
  }, [state])

  useEffect(() => {
    if (cooldown <= 0) return
    const id = window.setInterval(() => {
      setCooldown((c) => Math.max(0, c - 1))
    }, 1000)
    return () => window.clearInterval(id)
  }, [cooldown])

  // Move focus to the first error on render so screen-reader users hit it
  // immediately (and keyboard users can correct without re-tabbing).
  useEffect(() => {
    if (state.error && errorRef.current) errorRef.current.focus()
  }, [state])

  if (state.ok) {
    if (typeof window !== 'undefined') window.location.href = '/'
  }

  const submitDisabled = pending || cooldown > 0

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-lg border border-border bg-canvas p-8">
        <div className="mb-6 flex items-center gap-2">
          <Newspaper className="h-5 w-5 text-primary" />
          <h1 className="text-lg font-semibold">{t('title')}</h1>
        </div>
        <form action={action} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">{t('emailLabel')}</label>
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              disabled={submitDisabled}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none disabled:opacity-60"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">{t('passwordLabel')}</label>
            <input
              name="password"
              type="password"
              required
              minLength={8}
              autoComplete="current-password"
              disabled={submitDisabled}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none disabled:opacity-60"
            />
          </div>
          {state.error && (
            <p
              ref={errorRef}
              role="alert"
              aria-live="polite"
              tabIndex={-1}
              className="rounded-md border border-destructive/40 bg-surface px-3 py-2 text-sm text-destructive focus:outline-none"
            >
              {state.error}
              {state.code === 'rate_limited' && cooldown > 0 && (
                <span aria-live="polite" className="ml-1 font-medium tabular-nums">
                  {t('retryingIn', { n: cooldown })}
                </span>
              )}
            </p>
          )}
          <button
            type="submit"
            disabled={submitDisabled}
            aria-busy={pending}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {cooldown > 0 ? t('retryIn', { n: cooldown }) : pending ? t('submitting') : t('submit')}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          {t('noAccount')}{' '}
          <Link href="/register" className="text-primary hover:underline">
            {t('register')}
          </Link>
        </p>
      </div>
    </main>
  )
}
