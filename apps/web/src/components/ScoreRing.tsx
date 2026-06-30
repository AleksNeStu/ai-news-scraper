/**
 * ScoreRing — circular progress indicator for an article's LLM score (0..1).
 *
 * Two concentric SVG circles: an outer dim track, an inner cyan (or
 * tier-colored) arc whose length is proportional to the score. When
 * `score === null`, only the dim track renders — the arc is hidden.
 *
 * Accessibility:
 *   - `role="img"` and an `aria-label` describing the score percentage
 *     and the current `tier` (when known) so screen-reader users get a
 *     meaningful summary rather than raw geometry.
 *
 * Tier stroke colors:
 *   - must_read      → cyan-500
 *   - recommended    → blue-500
 *   - worth_a_look   → slate-400
 *   - low_priority   → slate-300
 */

import { cn } from '@/lib/utils'
import type { Tier } from '@ai-news-scraper/shared'

export interface ScoreRingProps {
  /** Score in `[0, 1]`. Pass `null` when the article has never been scored. */
  score: number | null
  /** Visual size. `sm` (24px) for inline list rows, `md` (40px) for hero cards. */
  size?: 'sm' | 'md'
  /** Render the numeric score label inside the circle (only on `md`). */
  showLabel?: boolean
  /** When provided, recolors the arc using the tier palette. */
  tier?: Tier | null
  className?: string
}

const TIER_STROKE: Record<Tier, string> = {
  must_read: 'stroke-cyan-500',
  recommended: 'stroke-blue-500',
  worth_a_look: 'stroke-slate-400',
  low_priority: 'stroke-slate-300',
}

export function ScoreRing({
  score,
  size = 'sm',
  showLabel = false,
  tier = null,
  className,
}: ScoreRingProps) {
  const px = size === 'md' ? 40 : 24
  const stroke = size === 'md' ? 3 : 2
  const r = (px - stroke) / 2
  const c = 2 * Math.PI * r

  // Clamp into [0, 1] so an out-of-range backend score degrades gracefully.
  const clamped = score == null ? null : Math.max(0, Math.min(1, score))
  const arcLength = clamped == null ? 0 : clamped * c
  const dashOffset = clamped == null ? c : c - arcLength

  const arcStroke = tier ? TIER_STROKE[tier] : 'stroke-[hsl(var(--primary))]'

  const ariaLabel =
    score == null
      ? 'Not yet scored'
      : `Score ${(score * 100).toFixed(0)} percent, tier ${tier ?? 'unknown'}`

  return (
    <svg
      role="img"
      aria-label={ariaLabel}
      width={px}
      height={px}
      viewBox={`0 0 ${px} ${px}`}
      className={cn('shrink-0', className)}
    >
      {/* Outer dim track. */}
      <circle
        cx={px / 2}
        cy={px / 2}
        r={r}
        fill="none"
        strokeWidth={stroke}
        className="stroke-[hsl(var(--border))]"
      />
      {/* Inner cyan arc — drawn regardless of `score` so the dash math stays in one place. */}
      <circle
        cx={px / 2}
        cy={px / 2}
        r={r}
        fill="none"
        strokeWidth={stroke}
        strokeLinecap="round"
        className={cn(arcStroke, clamped == null && 'opacity-0')}
        strokeDasharray={c}
        strokeDashoffset={dashOffset}
        transform={`rotate(-90 ${px / 2} ${px / 2})`}
      />
      {size === 'md' && showLabel && clamped != null && (
        <text
          x="50%"
          y="50%"
          dominantBaseline="central"
          textAnchor="middle"
          fontSize={size === 'md' ? '10' : '8'}
          className="fill-[hsl(var(--foreground))] font-medium tabular-nums"
        >
          {clamped.toFixed(2)}
        </text>
      )}
    </svg>
  )
}
