'use client'

/**
 * Server-confirmed logout button (ADR-015 §15.9 / H3).
 *
 * The button wraps the server action ``logoutAction`` from
 * ``@/lib/auth``. The server action does three things in order:
 *
 *   1. POSTs ``/auth/logout`` — the backend revokes the user's
 *      refresh-token row (per the ``refresh_tokens`` table per
 *      ADR-015 §15.9 / H3) and clears BOTH cookies on the response.
 *   2. On 2xx, clears the local ``auth_token`` cookie (the access
 *      JWT) and ``redirect('/login')``s.
 *   3. On 5xx, leaves the cookie intact and returns a discriminated
 *      error result.
 *
 * UX:
 *   - Click → button becomes disabled with a "Logging out…" label
 *     and ``aria-busy="true"`` while the action is in-flight.
 *   - On success the server redirects, so this client island
 *     unmounts before any further state change.
 *   - On failure the button re-enables and renders an inline error
 *     (role=alert, aria-live=polite) — the previous implementation
 *     silently cleared the cookie and bounced the user regardless.
 *
 * The button is a small client island inside ``AppHeader`` (a server
 * component). It does not own navigation; on success, the server
 * action ``redirect()``s and Next swaps the route.
 *
 * i18n (Task #32):
 *   - Button label + inline error come from `useTranslations('Auth.Logout')`.
 *     The action's `error` string flows from `logoutAction` via the
 *     server-side `localizeError` helper, so the inline fallback below
 *     only fires on browser-side action transport failures (network).
 */

import type { MouseEvent } from 'react'
import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { LogOut } from 'lucide-react'
import { logoutAction } from '@/lib/auth'
import { cn } from '@/lib/utils'

export function LogoutButton() {
  const t = useTranslations('Auth.Logout')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onClick(event: MouseEvent<HTMLButtonElement>) {
    const button = event.currentTarget
    setError(null)
    setPending(true)
    button.blur()
    try {
      // ``logoutAction`` returns ``never`` on success (it calls
      // ``redirect('/login')``), or a discriminated error object
      // on server-side failure. Wrap in try/catch to also catch
      // browser-side action transport errors.
      const result = await logoutAction()
      // If we reach this branch the server returned an error
      // result (the success branch has already redirected).
      if (result && typeof result === 'object' && 'ok' in result && result.ok === false) {
        setError(result.error)
      }
    } catch {
      // Browser-side action transport failure (network). Mirror
      // the server-error path so the user can retry.
      setError(t('failed'))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={pending}
        aria-busy={pending}
        className={cn(
          'inline-flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-primary/40',
          'disabled:cursor-not-allowed disabled:opacity-60'
        )}
      >
        <LogOut className="h-4 w-4" />
        {pending ? t('loggingOut') : t('logout')}
      </button>
      {error && (
        <p
          role="alert"
          aria-live="polite"
          className="rounded-md border border-destructive/40 bg-surface px-2 py-1 text-xs text-destructive"
        >
          {error}
        </p>
      )}
    </div>
  )
}
