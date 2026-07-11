'use client'

/**
 * EmbeddingsView — the client island for `/embeddings` (Task #34, ADR-022).
 *
 * Layout (3 columns on desktop, stacked on mobile):
 *   1. Model picker — fetches `GET /embeddings/providers` on mount and
 *      renders one row per provider. Each row carries a status badge:
 *        - green  "ready"     — supports_embed && key_configured
 *        - red    "no key"    — requires_own_key && !key_configured
 *        - gray   "no embed"  — !supports_embed
 *      Disabled providers (red / gray badges) are NOT selectable: the
 *      button is rendered but `aria-disabled` + `disabled` keep them out
 *      of the click stream. The picker state is exposed through
 *      data-testids so the page test can verify "disabled providers
 *      are not selectable" without driving a Radix-Select keyboard.
 *   2. Two text inputs ("Text A" / "Text B") + a "Compute similarity"
 *      button. The button is disabled until both inputs are non-empty.
 *      Each textarea is capped at 8000 chars (matches the backend
 *      cap from `apps/api/api/services/embedder.py:31`).
 *   3. Results — cosine similarity (big, color-coded by magnitude), plus
 *      two side-by-side VectorDisplay panels (one per text).
 *
 * 422 handling (ADR-022 §22.4 / §22.5):
 *   - `provider_does_not_support_embedding` → inline message
 *     "This model doesn't support embeddings".
 *   - `provider_key_missing` → inline message "API key not configured
 *     for this model — ask your admin to add it in settings".
 *   - `provider_unknown` → inline message "Unknown model — refresh the
 *     picker".
 *   Anything else → generic "Couldn't reach the server. Try again."
 *
 * Key-leak defense (ADR-022 §22.5): the only fields read off the
 * provider response are the documented TS shape (`id`, `display_name`,
 * `supports_embed`, `requires_own_key`, `key_configured`, `dimensions`,
 * `default_model`). We intentionally do NOT spread or destructure
 * any other field — even if a future API revision accidentally adds a
 * `key` field to the response, the picker never displays it.
 */

import * as React from 'react'
import { useTranslations } from 'next-intl'
import { AlertTriangle, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { VectorDisplay } from '@/components/VectorDisplay'
import {
  computeSimilarity,
  isProviderDoesNotSupportEmbedding,
  isProviderKeyMissing,
  isProviderUnknown,
  listEmbeddingProviders,
} from '@/lib/api/embeddings'
import { ApiError } from '@/lib/api'
import type { EmbeddingProvider, SimilarityResponse } from '@ai-news-scraper/shared'

const TEXT_CAP = 8000 // ADR-022 §22.2 + embedder.py:31

type Phase =
  | { kind: 'loading' }
  | { kind: 'providers-error'; message: string }
  | { kind: 'ready'; providers: EmbeddingProvider[] }
  | { kind: 'similarity-pending'; providers: EmbeddingProvider[] }
  | {
      kind: 'similarity-error'
      providers: EmbeddingProvider[]
      code: 'unsupported' | 'no-key' | 'unknown' | 'other'
      message: string
    }
  | { kind: 'similarity-done'; providers: EmbeddingProvider[]; response: SimilarityResponse }

export function EmbeddingsView() {
  const t = useTranslations('Embeddings')

  const [phase, setPhase] = React.useState<Phase>({ kind: 'loading' })
  const [providerId, setProviderId] = React.useState<string>('')
  const [textA, setTextA] = React.useState('')
  const [textB, setTextB] = React.useState('')

  // Fetch the provider list once on mount. We intentionally do NOT retry
  // on every render — the inventory is bounded by the LLM factory
  // (ADR-011 §11.4) and changes only when a deploy adds a provider.
  React.useEffect(() => {
    let cancelled = false
    setPhase({ kind: 'loading' })
    listEmbeddingProviders()
      .then((r) => {
        if (cancelled) return
        setPhase({ kind: 'ready', providers: r.providers })
        // Pre-select the first SELECTABLE provider so the user can
        // click "Compute" without an extra step. If none are selectable
        // (e.g. all keys missing), leave the picker empty — the form
        // button stays disabled until the user picks something valid.
        const selectable = r.providers.find((p) => p.supports_embed && p.key_configured)
        if (selectable) setProviderId(selectable.id)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        const msg = e instanceof Error ? e.message : t('error.network')
        setPhase({ kind: 'providers-error', message: msg })
      })
    return () => {
      cancelled = true
    }
  }, [t])

  const providers: EmbeddingProvider[] =
    phase.kind === 'ready'
      ? phase.providers
      : phase.kind === 'similarity-pending' ||
          phase.kind === 'similarity-error' ||
          phase.kind === 'similarity-done'
        ? phase.providers
        : []

  const selectedProvider = providers.find((p) => p.id === providerId) ?? null
  const isSelectable = (p: EmbeddingProvider) => p.supports_embed && p.key_configured

  const canSubmit =
    (phase.kind === 'ready' ||
      phase.kind === 'similarity-done' ||
      phase.kind === 'similarity-error') &&
    !!selectedProvider &&
    textA.trim().length > 0 &&
    textB.trim().length > 0

  const submitting = phase.kind === 'similarity-pending'

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit || !selectedProvider) return
    setPhase({ kind: 'similarity-pending', providers })
    computeSimilarity({
      provider_id: selectedProvider.id,
      text_a: textA,
      text_b: textB,
    })
      .then((response) => {
        setPhase({ kind: 'similarity-done', providers, response })
      })
      .catch((e: unknown) => {
        let code: 'unsupported' | 'no-key' | 'unknown' | 'other'
        let message: string
        if (isProviderDoesNotSupportEmbedding(e)) {
          code = 'unsupported'
          message = t('error.unsupported')
        } else if (isProviderKeyMissing(e)) {
          code = 'no-key'
          message = t('error.noKey')
        } else if (isProviderUnknown(e)) {
          code = 'unknown'
          message = t('error.unknown')
        } else if (e instanceof ApiError) {
          code = 'other'
          message = e.message || t('error.network')
        } else {
          code = 'other'
          message = t('error.network')
        }
        setPhase({ kind: 'similarity-error', providers, code, message })
      })
  }

  // ---- Render branches ----------------------------------------------------

  if (phase.kind === 'loading') {
    return (
      <div className="grid gap-6 px-6 py-10 lg:grid-cols-3" data-testid="embeddings-loading">
        <div className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
        <div className="space-y-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
        <div className="space-y-3">
          <Skeleton className="h-10 w-40" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    )
  }

  if (phase.kind === 'providers-error') {
    return (
      <div className="px-6 py-10" role="alert">
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" aria-hidden="true" />
          <div className="text-sm">
            <p className="font-medium">{t('error.title')}</p>
            <p className="text-muted-foreground">{phase.message}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <form
      onSubmit={onSubmit}
      className="grid gap-6 px-6 py-10 lg:grid-cols-3"
      data-testid="embeddings-view"
    >
      {/* ---- LEFT COLUMN: model picker --------------------------------- */}
      <section aria-labelledby="provider-heading" className="space-y-3">
        <h3 id="provider-heading" className="text-sm font-medium">
          {t('picker.heading')}
        </h3>
        <ul className="space-y-2" role="radiogroup" aria-labelledby="provider-heading">
          {providers.map((p) => {
            const selectable = isSelectable(p)
            const selected = providerId === p.id
            const badge = badgeFor(p, t)
            return (
              <li key={p.id}>
                <button
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  aria-disabled={!selectable}
                  disabled={!selectable}
                  onClick={() => {
                    if (selectable) setProviderId(p.id)
                  }}
                  data-testid={`provider-${p.id}`}
                  data-selectable={selectable ? 'true' : 'false'}
                  className={
                    'flex w-full items-start justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm transition ' +
                    (selected
                      ? 'border-primary bg-primary/5'
                      : 'border-border bg-canvas hover:border-primary/40') +
                    (selectable ? '' : ' cursor-not-allowed opacity-60')
                  }
                >
                  <span className="min-w-0">
                    <span className="block font-medium">{p.display_name}</span>
                    {p.default_model && (
                      <span className="block truncate text-xs text-muted-foreground">
                        {p.default_model}
                        {p.dimensions != null ? ` · ${p.dimensions} dims` : ''}
                      </span>
                    )}
                  </span>
                  <span
                    aria-label={badge.label}
                    className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${badge.className}`}
                    data-testid={`provider-${p.id}-badge`}
                  >
                    {badge.label}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      {/* ---- MIDDLE COLUMN: text inputs + button ----------------------- */}
      <section aria-labelledby="inputs-heading" className="space-y-3">
        <h3 id="inputs-heading" className="sr-only">
          {t('inputs.heading')}
        </h3>

        <label className="block space-y-1">
          <span className="text-sm font-medium">{t('inputs.textA')}</span>
          <textarea
            value={textA}
            onChange={(e) => setTextA(e.target.value)}
            maxLength={TEXT_CAP}
            rows={6}
            placeholder={t('inputs.placeholderA')}
            data-testid="text-a"
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <span className="text-xs text-muted-foreground">
            {textA.length} / {TEXT_CAP}
          </span>
        </label>

        <label className="block space-y-1">
          <span className="text-sm font-medium">{t('inputs.textB')}</span>
          <textarea
            value={textB}
            onChange={(e) => setTextB(e.target.value)}
            maxLength={TEXT_CAP}
            rows={6}
            placeholder={t('inputs.placeholderB')}
            data-testid="text-b"
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <span className="text-xs text-muted-foreground">
            {textB.length} / {TEXT_CAP}
          </span>
        </label>

        <Button
          type="submit"
          disabled={!canSubmit || submitting}
          data-testid="submit-similarity"
          className="w-full sm:w-auto"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              {t('inputs.submitting')}
            </>
          ) : (
            t('inputs.submit')
          )}
        </Button>

        {phase.kind === 'similarity-error' && (
          <p
            role="alert"
            data-testid={`error-${phase.code}`}
            className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm"
          >
            {phase.message}
          </p>
        )}
      </section>

      {/* ---- RIGHT COLUMN: results ------------------------------------- */}
      <section aria-labelledby="results-heading" className="space-y-4">
        <h3 id="results-heading" className="text-sm font-medium">
          {t('results.heading')}
        </h3>

        {phase.kind === 'similarity-pending' && (
          <Skeleton className="h-12 w-40" data-testid="results-loading" />
        )}

        {phase.kind === 'similarity-done' && (
          <>
            <SimilarityScore
              value={phase.response.cosine_similarity}
              label={t('results.cosine')}
              testId="cosine-score"
            />
            <div className="space-y-3">
              <VectorDisplay
                vector={phase.response.vector_a}
                label={`${t('results.vectorA')} · ${phase.response.model}`}
                testId="vector-a"
              />
              <VectorDisplay
                vector={phase.response.vector_b}
                label={`${t('results.vectorB')} · ${phase.response.model}`}
                testId="vector-b"
              />
            </div>
            {(phase.response.dot_product != null || phase.response.euclidean != null) && (
              <dl
                className="grid grid-cols-2 gap-2 rounded-md border border-border bg-canvas p-3 text-xs"
                data-testid="bonus-metrics"
              >
                {phase.response.dot_product != null && (
                  <>
                    <dt className="text-muted-foreground">{t('results.dotProduct')}</dt>
                    <dd className="font-mono">{phase.response.dot_product.toFixed(4)}</dd>
                  </>
                )}
                {phase.response.euclidean != null && (
                  <>
                    <dt className="text-muted-foreground">{t('results.euclidean')}</dt>
                    <dd className="font-mono">{phase.response.euclidean.toFixed(4)}</dd>
                  </>
                )}
              </dl>
            )}
          </>
        )}

        {phase.kind === 'ready' && (
          <p className="text-sm text-muted-foreground" data-testid="results-empty">
            {t('results.empty')}
          </p>
        )}
      </section>
    </form>
  )
}

/** Pick the status badge for a provider row. */
function badgeFor(
  p: EmbeddingProvider,
  t: ReturnType<typeof useTranslations<'Embeddings'>>
): { label: string; className: string } {
  if (p.supports_embed && p.key_configured) {
    return {
      label: t('picker.ready'),
      className: 'bg-green-500/15 text-green-700 dark:text-green-300',
    }
  }
  if (!p.supports_embed) {
    return { label: t('picker.noEmbed'), className: 'bg-muted text-muted-foreground' }
  }
  // requires_own_key && !key_configured
  return { label: t('picker.noKey'), className: 'bg-destructive/15 text-destructive' }
}

/** Big color-coded cosine number. */
function SimilarityScore({
  value,
  label,
  testId,
}: {
  value: number
  label: string
  testId: string
}) {
  const tone =
    value > 0.7
      ? 'text-green-600 dark:text-green-300'
      : value >= 0.3
        ? 'text-yellow-600 dark:text-yellow-300'
        : 'text-muted-foreground'
  return (
    <div className="rounded-lg border border-border bg-canvas p-4" data-testid={testId}>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p
        className={`mt-1 font-mono text-3xl font-semibold ${tone}`}
        data-testid={`${testId}-value`}
      >
        {value.toFixed(4)}
      </p>
    </div>
  )
}
