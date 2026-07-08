import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useFilterUrl } from '@/components/filters/useFilterUrl'

const replaceSpy = vi.fn()
let mockSearch = ''

vi.mock('@/i18n/navigation', () => ({
  useRouter: () => ({ replace: replaceSpy }),
  usePathname: () => '/search',
  useSearchParams: () => new URLSearchParams(mockSearch),
}))

describe('useFilterUrl', () => {
  beforeEach(() => {
    replaceSpy.mockReset()
    mockSearch = ''
  })

  function render() {
    return renderHook(() => useFilterUrl())
  }

  function lastUrl(): string {
    const calls = replaceSpy.mock.calls
    return calls[calls.length - 1][0]
  }

  it('set(key, value) writes ?key=value and drops ?page', () => {
    mockSearch = '?q=ai&page=3'
    const { result } = render()
    act(() => result.current.set('source', 'techcrunch.com'))
    const url = lastUrl()
    expect(url).toContain('source=techcrunch.com')
    expect(url).not.toContain('page=')
    expect(url).toContain('q=ai')
  })

  it('set(key, null) removes the key without dropping page', () => {
    mockSearch = '?source=techcrunch.com&page=2'
    const { result } = render()
    act(() => result.current.set('source', null))
    const url = lastUrl()
    expect(url).not.toContain('source=')
    expect(url).not.toContain('page=')
  })

  it('append adds a second value to a repeatable key', () => {
    mockSearch = '?topic=ai'
    const { result } = render()
    act(() => result.current.append('topic', 'rag'))
    const url = lastUrl()
    expect(url).toContain('topic=ai')
    expect(url).toContain('topic=rag')
  })

  it('remove(key) drops every occurrence', () => {
    mockSearch = '?topic=ai&topic=rag&topic=ml'
    const { result } = render()
    act(() => result.current.remove('topic'))
    const url = lastUrl()
    expect(url).not.toContain('topic=')
  })

  it('remove(key, value) drops only that value, keeps others', () => {
    mockSearch = '?topic=ai&topic=rag'
    const { result } = render()
    act(() => result.current.remove('topic', 'ai'))
    const url = lastUrl()
    expect(url).toContain('topic=rag')
    expect(url).not.toContain('topic=ai')
  })

  it('reset([keys]) drops every key in the list, preserves others', () => {
    mockSearch = '?q=foo&source=x&topic=ai&page=2'
    const { result } = render()
    act(() => result.current.reset(['source', 'topic']))
    const url = lastUrl()
    expect(url).not.toContain('source=')
    expect(url).not.toContain('topic=')
    expect(url).toContain('q=foo')
  })

  it('get reads a single value', () => {
    mockSearch = '?source=techcrunch.com'
    const { result } = render()
    expect(result.current.get('source')).toBe('techcrunch.com')
    expect(result.current.get('missing')).toBeNull()
  })

  it('getAll reads every value of a repeatable key', () => {
    mockSearch = '?topic=ai&topic=rag'
    const { result } = render()
    expect(result.current.getAll('topic')).toEqual(['ai', 'rag'])
  })

  it('preserves unrelated params across mutations', () => {
    mockSearch = '?q=foo&page_size=10&source=x'
    const { result } = render()
    act(() => result.current.set('from', '2026-01-01'))
    const url = lastUrl()
    expect(url).toContain('q=foo')
    expect(url).toContain('page_size=10')
    expect(url).toContain('source=x')
    expect(url).toContain('from=2026-01-01')
  })

  it('does not scroll to top on replace', () => {
    mockSearch = ''
    const { result } = render()
    act(() => result.current.set('q', 'ai'))
    const opts = replaceSpy.mock.calls[replaceSpy.mock.calls.length - 1][1]
    expect(opts).toEqual({ scroll: false })
  })
})
