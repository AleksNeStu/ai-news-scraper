/**
 * Skeleton fallback for the public share page (Task #33, ADR-021).
 *
 * Mirrors the layout of `ShareView` so the rendered fallback does not
 * cause a layout shift once the real content arrives. Uses the shared
 * `<Skeleton />` primitive from `@/components/ui/skeleton`.
 */

import { Skeleton } from '@/components/ui/skeleton'

export function ShareSkeleton() {
  return (
    <main className="min-h-screen" data-testid="share-skeleton">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-9 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-6 w-16" />
          <Skeleton className="h-6 w-20" />
          <Skeleton className="h-6 w-12" />
        </div>
      </div>
    </main>
  )
}
