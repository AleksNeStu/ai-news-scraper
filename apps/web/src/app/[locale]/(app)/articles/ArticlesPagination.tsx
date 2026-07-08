'use client'

/**
 * Thin client-side wrapper around the shared <Pagination> widget
 * that wires onPageChange to a router.replace with the new ?page=.
 *
 * The /articles page is a Server Component; it can't pass an
 * `onPageChange` callback into a Client Component that calls
 * useRouter internally. ArticlesPagination is the bridge: a tiny
 * Client Component that owns the URL write and delegates everything
 * else to the shared widget.
 */

import { useRouter, usePathname, useSearchParams } from '@/i18n/navigation'
import { Pagination } from '@/components/Pagination'

export interface ArticlesPaginationProps {
  page: number
  totalPages: number
}

export function ArticlesPagination({ page, totalPages }: ArticlesPaginationProps) {
  const router = useRouter()
  const pathname = usePathname()
  const search = useSearchParams()

  function onPageChange(next: number) {
    const params = new URLSearchParams(search?.toString() ?? '')
    if (next === 1) params.delete('page')
    else params.set('page', String(next))
    const qs = params.toString()
    const url = (qs ? `${pathname}?${qs}` : pathname) as never
    router.replace(url, { scroll: false })
  }

  return <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />
}
