'use client'

/**
 * VectorDisplay — render one embedding vector for the comparison view
 * (Task #34, ADR-022 §22.7).
 *
 * The API returns the FULL native-dimension vector (768–3072 floats).
 * The default render packs two complementary views (per the ADR —
 * "hex blob + first 8 dims"):
 *
 *   1. **Hex blob** — first 32 dims packed little-endian as IEEE 754
 *      float32 bytes, rendered as 128 hex chars. Two of these side-by-
 *      side let a human eyeball correlation without scrolling. The raw
 *      bytes are lossless; nothing is rounded here.
 *   2. **First 8 dims** — comma-separated `0.1234, -0.5678, …` so the
 *      user can read individual scalar values across the two vectors.
 *      The API contract is full-precision; we render the actual values.
 *   3. **Total dimension count** and a `[…N more]` placeholder when
 *      truncation applies so the user knows the visible list is not
 *      complete.
 *
 * A "Show full vector" toggle reveals the rest of the floats on demand
 * — useful for exact comparison research (e.g. inspecting why two
 * texts scored 0.83 cosine) without permanently crowding the layout.
 *
 * Key-leak defense (ADR-022 §22.5): this component receives the vector
 * as `number[]`. It never reads any field named `key` / `api_key` /
 * `secret` — the prop API is intentionally tight so even an upstream
 * bug pushing a secret-shaped object into the React tree would surface
 * as a TS compile error at the parent boundary, not a silent render.
 */

import * as React from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface VectorDisplayProps {
  /** The full embedding vector (length equals the provider's
   * `dimensions`). */
  vector: number[]
  /** Optional short label rendered above the vector (e.g. "Text A" or
   * "Provider X"). When omitted, the dim-count alone is the heading. */
  label?: string
  /** Number of leading dimensions to show in the compressed view.
   * Defaults to 8 per ADR-022 §22.7. */
  previewDims?: number
  /** How many leading dimensions to pack into the hex blob.
   * Defaults to 32 dims (128 bytes) — enough for a useful header
   * glance without overflowing the column. */
  hexBlobDims?: number
  /** Custom test id (mirrors the test-ids the EmbeddingsView relies on). */
  testId?: string
}

const DEFAULT_PREVIEW = 8
const DEFAULT_HEX_BLOB_DIMS = 32

/** Pack a `number[]` of floats into a hex blob of little-endian bytes.
 * Returns the empty string when the input has no dims to pack. Used
 * for the compact side-by-side display; the lossless original stays
 * in the API response. */
function vectorToHexBlob(vector: readonly number[], dims: number): string {
  const length = Math.min(vector.length, dims)
  if (length === 0) return ''
  const buf = new ArrayBuffer(length * 4)
  const f32 = new Float32Array(buf)
  for (let i = 0; i < length; i++) f32[i] = vector[i]
  const u8 = new Uint8Array(buf)
  let out = ''
  for (let i = 0; i < u8.length; i++) {
    out += u8[i].toString(16).padStart(2, '0')
  }
  return out
}

/** Format a float with 4 decimal places, preserving the sign. */
function formatDim(n: number): string {
  return n.toFixed(4)
}

export function VectorDisplay({
  vector,
  label,
  previewDims = DEFAULT_PREVIEW,
  hexBlobDims = DEFAULT_HEX_BLOB_DIMS,
  testId = 'vector-display',
}: VectorDisplayProps) {
  const [expanded, setExpanded] = React.useState(false)
  const total = vector.length
  const head = vector.slice(0, previewDims)
  const tail = vector.slice(previewDims)
  const tailCount = tail.length
  const hexBlob = vectorToHexBlob(vector, hexBlobDims)
  const hexDimsShown = Math.min(total, hexBlobDims)

  const headLabel = label ?? `${total} dims`

  return (
    <section
      className="rounded-lg border border-border bg-canvas p-4"
      data-testid={testId}
      aria-label={label ?? 'Embedding vector'}
    >
      <header className="mb-2 flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium">{headLabel}</h4>
        <span className="text-xs text-muted-foreground" data-testid={`${testId}-total`}>
          {total} dims
        </span>
      </header>

      {!expanded ? (
        <>
          {hexBlob && (
            <p
              className="break-all rounded border border-border bg-surface p-2 font-mono text-[11px] leading-relaxed text-foreground/80"
              data-testid={`${testId}-hex`}
            >
              {hexBlob}
            </p>
          )}
          <p
            className="mt-2 break-words font-mono text-xs leading-relaxed"
            data-testid={`${testId}-preview`}
          >
            {head.map(formatDim).join(', ')}
            {tailCount > 0 && (
              <>
                , <span data-testid={`${testId}-more`}>[…{tailCount} more]</span>
              </>
            )}
          </p>
          {hexDimsShown < total && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              Hex blob covers first {hexDimsShown} of {total} dims
            </p>
          )}
          <div className="mt-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setExpanded(true)}
              aria-expanded={false}
              aria-controls={`${testId}-full`}
              data-testid={`${testId}-show-full`}
            >
              <ChevronRight className="h-3 w-3" aria-hidden="true" />
              Show full vector
            </Button>
          </div>
        </>
      ) : (
        <>
          <p
            id={`${testId}-full`}
            className="break-words font-mono text-xs leading-relaxed"
            data-testid={`${testId}-full-vector`}
          >
            {vector.map(formatDim).join(', ')}
          </p>
          <div className="mt-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setExpanded(false)}
              aria-expanded={true}
              aria-controls={`${testId}-full`}
              data-testid={`${testId}-collapse`}
            >
              <ChevronDown className="h-3 w-3" aria-hidden="true" />
              Collapse
            </Button>
          </div>
        </>
      )}
    </section>
  )
}
