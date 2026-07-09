'use client'

/**
 * Register page (H1 / ADR-015 §15.7 + Task #32).
 *
 * Surfaces Pydantic v2 422 field errors from ``/auth/register``. With the
 * ``extra="forbid"`` policy on ``UserCreate`` (per ADR-015), a request body
 * that includes an unknown field (e.g. ``{\"email\": ..., \"password\": ...,
 * \"is_admin\": true}``) returns 422 with a problem+json ``detail`` array
 * shaped like:
 *
 *   [{type: "extra_forbidden", loc: ["body", "is_admin"],
 *     msg: "Extra inputs are not permitted", input: true}, ...]
 *
 * The register action parses that array (see ``parsePydanticFieldErrors`` in
 * ``@/lib/auth``) into a ``{ field: message }`` map and the form renders one
 * row per rejected field. For the common case of a single field-error the
 * message reads \"is_admin: Extra inputs are not permitted\" — useful for
 * users who tampered with the request and hit the schema guard, and
 * consistent with the inline error shape used on the login page.
 *
 * i18n (Task #32): strings come from `useTranslations('Auth.Register')`,
 * locale is passed into `registerAction` as the third arg.
 */

import { useActionState, useEffect, useRef } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Newspaper } from 'lucide-react'
import { Link } from '@/i18n/navigation'
import { registerAction, type RegisterState } from '@/lib/auth'

const initialState: RegisterState = { ok: false }

export default function RegisterPage() {
  const t = useTranslations('Auth.Register')
  const locale = useLocale()
  const [state, action, pending] = useActionState(
    async (prev: RegisterState, formData: FormData) => registerAction(prev, formData, locale),
    initialState
  )
  const errorRef = useRef<HTMLDivElement | null>(null)

  // Move focus to the first error on render so screen-reader users hit it
  // immediately and keyboard users can correct without re-tabbing. Same
  // pattern as the login page.
  useEffect(() => {
    if ((state.error || state.fieldErrors) && errorRef.current) {
      errorRef.current.focus()
    }
  }, [state])

  if (state.ok && typeof window !== 'undefined') {
    window.location.href = '/'
  }

  const hasFieldErrors = !!state.fieldErrors && Object.keys(state.fieldErrors).length > 0

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-lg border border-border bg-canvas p-8">
        <div className="mb-6 flex items-center gap-2">
          <Newspaper className="h-5 w-5 text-primary" />
          <h1 className="text-lg font-semibold">{t('title')}</h1>
        </div>
        <form action={action} className="space-y-4">
          <div>
            <label htmlFor="register-email" className="mb-1 block text-sm text-muted-foreground">
              {t('emailLabel')}
            </label>
            <input
              id="register-email"
              name="email"
              type="email"
              required
              autoComplete="email"
              aria-invalid={hasFieldErrors && !!state.fieldErrors?.email ? true : undefined}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none aria-invalid:border-destructive"
            />
            {hasFieldErrors && state.fieldErrors?.email && (
              <p className="mt-1 text-xs text-destructive">{state.fieldErrors.email}</p>
            )}
          </div>
          <div>
            <label htmlFor="register-password" className="mb-1 block text-sm text-muted-foreground">
              {t('passwordLabel')}
            </label>
            <input
              id="register-password"
              name="password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              aria-invalid={hasFieldErrors && !!state.fieldErrors?.password ? true : undefined}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none aria-invalid:border-destructive"
            />
            {hasFieldErrors && state.fieldErrors?.password && (
              <p className="mt-1 text-xs text-destructive">{state.fieldErrors.password}</p>
            )}
          </div>
          {(state.error || hasFieldErrors) && (
            <div
              ref={errorRef}
              role="alert"
              aria-live="polite"
              tabIndex={-1}
              className="rounded-md border border-destructive/40 bg-surface px-3 py-2 text-sm text-destructive focus:outline-none"
            >
              {state.error && <p>{state.error}</p>}
              {/* H1: render any field errors that did NOT map onto the
                  email / password inputs (e.g. ``is_admin`` when the
                  ``extra="forbid"`` schema guard rejects it). The shape
                  reads ``field: Pydantic message`` so the user knows
                  which key the backend refused. */}
              {hasFieldErrors &&
                Object.entries(state.fieldErrors!)
                  .filter(([field]) => field !== 'email' && field !== 'password')
                  .map(([field, msg]) => (
                    <p key={field} className="font-mono text-xs">
                      <span className="font-semibold">{field}:</span> {msg}
                    </p>
                  ))}
            </div>
          )}
          <button
            type="submit"
            disabled={pending}
            aria-busy={pending}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t('submitting') : t('submit')}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          {t('haveAccount')}{' '}
          <Link href="/login" className="text-primary hover:underline">
            {t('signIn')}
          </Link>
        </p>
      </div>
    </main>
  )
}
