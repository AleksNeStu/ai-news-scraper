'use client'

/**
 * One-click unsubscribe landing page (RFC 8058 §3.2 + Task #32).
 *
 * Public route — no auth. The signed JWT in `?token=` is the credential;
 * `?digest_id=` identifies which digest to flip `email_digest_enabled` for.
 *
 * On mount we auto-submit (no manual click required by the RFC). While the
 * POST is in flight we render a "Working…" state; on completion we show
 * confirmation based on the server's `UnsubscribeResponse`:
 *   - `unsubscribed: true`  → "You've been unsubscribed"
 *   - `unsubscribed: false` → "You were already unsubscribed on {at}"
 *
 * Errors:
 *   - Missing digest_id / token → explain the link is malformed.
 *   - 4xx from backend (expired token, replay) → show the detail message.
 *   - Network / 5xx → "Couldn't reach the server. Try again from the email."
 *
 * i18n (Task #32): every user-visible string comes from
 * `useTranslations('Unsubscribe')`. The timestamp formatting is locale-aware
 * via `formatTimestamp(at, locale)` from `lib/utils`.
 */

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { CheckCircle2, MailMinus, AlertTriangle } from 'lucide-react'
import { Link } from '@/i18n/navigation'
import { unsubscribeDigest } from '@/lib/api/digest'
import { ApiError } from '@/lib/api'
import { formatTimestamp } from '@/lib/utils'

type Phase =
  | { kind: 'idle' }
  | { kind: 'pending' }
  | { kind: 'ok'; unsubscribed: boolean; at: string }
  | { kind: 'error'; message: string }

export default function UnsubscribeForm() {
  const t = useTranslations('Unsubscribe')
  const locale = useLocale()
  const search = useSearchParams()
  const digestId = search?.get('digest_id') ?? ''
  const token = search?.get('token') ?? ''
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })

  useEffect(() => {
    if (phase.kind !== 'idle') return
    if (!digestId || !token) {
      setPhase({
        kind: 'error',
        message: t('error.invalidLink'),
      })
      return
    }
    setPhase({ kind: 'pending' })
    let cancelled = false
    unsubscribeDigest(digestId, token)
      .then((res) => {
        if (cancelled) return
        setPhase({ kind: 'ok', unsubscribed: res.unsubscribed, at: res.at })
      })
      .catch((e) => {
        if (cancelled) return
        const msg = e instanceof ApiError ? e.message : t('error.network')
        setPhase({ kind: 'error', message: msg })
      })
    return () => {
      cancelled = true
    }
  }, [digestId, token, phase.kind, t])

  return (
    <main className="min-h-screen">
      <div className="mx-auto flex max-w-md flex-col items-center px-6 py-20 text-center">
        <MailMinus className="mb-4 h-10 w-10 text-primary" />
        <h1 className="headline-serif text-2xl">{t('title')}</h1>

        <div className="mt-8 w-full">
          {phase.kind === 'idle' || phase.kind === 'pending' ? (
            <p className="text-sm text-muted-foreground">{t('working')}</p>
          ) : phase.kind === 'ok' ? (
            phase.unsubscribed ? (
              <SuccessCard
                title={t('success.title')}
                body={t('success.body')}
                at={phase.at}
                locale={locale}
                t={t}
              />
            ) : (
              <SuccessCard
                title={t('already.title')}
                body={t('already.body')}
                at={phase.at}
                locale={locale}
                t={t}
              />
            )
          ) : (
            <ErrorCard message={phase.message} t={t} />
          )}
        </div>

        <Link href="/login" className="mt-10 inline-flex min-h-6 items-center px-3 text-sm text-muted-foreground hover:text-primary">
          {t('backToApp')}
        </Link>
      </div>
    </main>
  )
}

type T = ReturnType<typeof useTranslations<'Unsubscribe'>>

function SuccessCard({
  title,
  body,
  at,
  locale,
  t,
}: {
  title: string
  body?: string
  at: string
  locale: string
  t: T
}) {
  return (
    <div className="rounded-lg border border-border bg-canvas p-6">
      <CheckCircle2 className="mx-auto mb-3 h-6 w-6 text-success" />
      <h2 className="font-medium">{title}</h2>
      {body && <p className="mt-1 text-sm text-muted-foreground">{body}</p>}
      <p className="mt-3 text-xs text-muted-foreground">
        {t('confirmedAt', { time: formatTimestamp(at, locale) })}
      </p>
    </div>
  )
}

function ErrorCard({ message, t }: { message: string; t: T }) {
  return (
    <div className="rounded-lg border border-destructive/40 bg-canvas p-6">
      <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-destructive" />
      <h2 className="font-medium">{t('error.title')}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
    </div>
  )
}
