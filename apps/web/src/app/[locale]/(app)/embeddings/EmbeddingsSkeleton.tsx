/**
 * Skeleton fallback for /embeddings (Task #34, ADR-022).
 *
 * Mirrors the 3-column layout of <EmbeddingsView/> so the rendered
 * fallback does not cause a layout shift once the real content arrives.
 * Uses the shared `<Skeleton />` primitive from `@/components/ui/skeleton`.
 */

import { Skeleton } from '@/components/ui/skeleton'

export function EmbeddingsSkeleton() {
  return (
    <div
      className="grid gap-6 px-6 py-10 lg:grid-cols-3"
      data-testid="embeddings-skeleton"
      aria-hidden="true"
    >
      {/* Left column — model picker */}
      <div className="space-y-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>

      {/* Middle column — text inputs + button */}
      <div className="space-y-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-9 w-44" />
      </div>

      {/* Right column — results */}
      <div className="space-y-3">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    </div>
  )
}
