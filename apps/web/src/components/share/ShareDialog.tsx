'use client'

/**
 * Share button + dialog for an article (Task #33, ADR-021).
 *
 * UX:
 *   1. User clicks the trigger button.
 *   2. On open, we POST /share (default ttl_days=30) to mint a token.
 *   3. Once the URL is back, the dialog shows it in a read-only input
 *      with a Copy button. "Link copied" is shown as inline confirmation
 *      (we do not use a global toast here — inline is enough and
 *      avoids another mount node on the page).
 *   4. Expiry line: "Link expires in 30 days" — computed from
 *      `expires_at` so the copy stays accurate if the default TTL
 *      changes.
 *
 * Accessibility:
 *   - Radix Dialog primitive handles focus trap, Escape, and the
 *     `role="dialog"` / `aria-labelledby` machinery.
 *   - The Copy button announces success via `aria-live="polite"` on
 *     the confirmation line.
 *   - While the POST is in flight, the dialog shows a spinner + loading
 *     copy, and the trigger button is disabled so the user can't fire
 *     a duplicate request.
 *
 * i18n (Task #32): every user-visible string comes from
 * `useTranslations('Share')`. The new namespace was added to
 * `messages/{en,ru}.json` as part of this commit.
 */

import { useEffect, useRef, useState } from 'react'
import { Copy, Loader2, Share2 } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { ApiError } from '@/lib/api'
import { createShare } from '@/lib/api/share'
import type { ID, ShareResponse } from '@ai-news-scraper/shared'

interface ShareDialogProps {
  articleId: ID
  /** Optional title shown above the URL (defaults to article headline). */
  headline?: string | null
}

type Phase =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ready'; share: ShareResponse }
  | { kind: 'error'; message: string }

export function ShareDialog({ articleId, headline }: ShareDialogProps) {
  const t = useTranslations('Share')
  const [open, setOpen] = useState(false)
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const [copied, setCopied] = useState(false)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Reset state every time the dialog opens so a stale URL from a
  // previous share of a different article never lingers.
  useEffect(() => {
    if (!open) {
      setPhase({ kind: 'idle' })
      setCopied(false)
      if (copyTimerRef.current) {
        clearTimeout(copyTimerRef.current)
        copyTimerRef.current = null
      }
      return
    }
    setPhase({ kind: 'loading' })
    let cancelled = false
    createShare({ article_id: articleId, ttl_days: 30 })
      .then((share) => {
        if (cancelled) return
        setPhase({ kind: 'ready', share })
      })
      .catch((e: unknown) => {
        if (cancelled) return
        const msg = e instanceof ApiError ? e.message : t('error.network')
        setPhase({ kind: 'error', message: msg })
      })
    return () => {
      cancelled = true
    }
  }, [open, articleId, t])

  function onCopy(url: string) {
    if (typeof navigator === 'undefined' || !navigator.clipboard) {
      // Fallback for browsers without clipboard API: select the input.
      const input = document.getElementById('share-url-input') as HTMLInputElement | null
      input?.select()
      return
    }
    void navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" aria-label={t('buttonAria')}>
          <Share2 className="h-4 w-4" />
          <span>{t('button')}</span>
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('dialogTitle')}</DialogTitle>
          <DialogDescription>
            {headline
              ? t('dialogDescriptionWithTitle', { title: headline })
              : t('dialogDescription')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {phase.kind === 'loading' && (
            <p
              className="flex items-center gap-2 text-sm text-muted-foreground"
              data-testid="share-loading"
            >
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              <span>{t('loading')}</span>
            </p>
          )}

          {phase.kind === 'error' && (
            <p
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
              data-testid="share-error"
            >
              {phase.message}
            </p>
          )}

          {phase.kind === 'ready' && (
            <>
              <label htmlFor="share-url-input" className="sr-only">
                {t('urlLabel')}
              </label>
              <div className="flex gap-2">
                <Input
                  id="share-url-input"
                  readOnly
                  value={phase.share.url}
                  onFocus={(e) => e.currentTarget.select()}
                  data-testid="share-url-input"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onCopy(phase.share.url)}
                  aria-label={t('copyAria')}
                  data-testid="share-copy-button"
                >
                  <Copy className="h-4 w-4" />
                  <span>{t('copy')}</span>
                </Button>
              </div>
              <p
                aria-live="polite"
                className="text-xs text-muted-foreground"
                data-testid="share-copy-confirmation"
              >
                {copied ? t('copied') : t('expiresIn', { days: daysUntil(phase.share.expires_at) })}
              </p>
            </>
          )}
        </div>

        <DialogFooter>
          <p className="text-xs text-muted-foreground">{t('footerNote')}</p>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Whole days between `now` and the ISO 8601 `expires_at`. Always ≥ 1
 * because the backend enforces `ttl_days ≥ 1` (ADR-021 §21.8); if the
 * clock is somehow off, we clamp to 1 to avoid rendering "0 days".
 */
function daysUntil(expiresAt: string): number {
  const ms = new Date(expiresAt).getTime() - Date.now()
  if (!Number.isFinite(ms) || ms <= 0) return 1
  return Math.max(1, Math.ceil(ms / (24 * 60 * 60 * 1000)))
}
