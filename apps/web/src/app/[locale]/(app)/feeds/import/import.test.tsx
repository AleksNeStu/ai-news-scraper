/**
 * Tests for the /feeds/import page (Task #35, ADR-024).
 *
 * Covers the seven observable guarantees the page delivers:
 *   1. Initial render — file picker visible, no preview, no submit.
 *   2. Flat OPML parses into 3 checkboxes.
 *   3. Nested OPML (Feedly category folders) groups feeds by parent path.
 *   4. Malformed XML surfaces the localised error; no preview shown.
 *   5. Select all / Deselect all toggles every checkbox.
 *   6. Submit POSTs ONLY the SELECTED subset (deselect one of three, body has 2).
 *   7. Success response renders all three badges, failed-list, and link.
 *   8. Russian locale renders without "missing message" warnings.
 *
 * Mocks `api.post` directly (no MSW in the test stack). Mocks
 * `DOMParser` against the actual `window.DOMParser` to keep the
 * `parseFromString` call realistic.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { IntlWrapper } from '@/test-utils/intl-helper'
import ImportPage from './page'
import { api, ApiError } from '@/lib/api'
import type * as ApiModule from '@/lib/api'
import type { BulkImportRequest, BulkImportResult } from '@ai-news-scraper/shared'

// `Link` from `@/i18n/navigation` is built on top of `next/navigation` +
// next-intl's createNavigation. jsdom doesn't resolve the underlying
// `next/navigation.js` import that createNavigation performs in dev
// (see register.test.tsx for the same workaround). Stub Link as a plain
// anchor — we only assert href + text, no client-side routing.
vi.mock('@/i18n/navigation', () => ({
  Link: ({
    href,
    children,
    className,
  }: {
    href: string
    children: React.ReactNode
    className?: string
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof ApiModule>('@/lib/api')
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
      postWithHeaders: vi.fn(),
      delete: vi.fn(),
    },
  }
})

const postMock = vi.mocked(api.post)

const SAMPLE_OPML = `<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Test export</title></head>
  <body>
    <outline type="rss" text="Hacker News" xmlUrl="https://news.ycombinator.com/rss"/>
    <outline type="rss" text="Lobsters" xmlUrl="https://lobste.rs/rss"/>
    <outline text="Tech">
      <outline type="rss" text="GitHub Blog" xmlUrl="https://github.blog/feed/"/>
    </outline>
  </body>
</opml>`

const MALFORMED_XML = `not xml at all <<< >>>`

interface FileWithText extends File {
  __testContent?: string
}

// jsdom v25 doesn't implement `Blob.prototype.text`, which the import page
// uses to read the uploaded OPML. Polyfill it via a side-channel: the
// `makeFile` helper stashes the source string on the File under a private
// property, and the polyfill returns that.
if (typeof Blob.prototype.text !== 'function') {
  // eslint-disable-next-line no-extend-native
  Blob.prototype.text = function (this: Blob) {
    const stash = (this as unknown as FileWithText).__testContent
    return Promise.resolve(typeof stash === 'string' ? stash : '')
  }
}

function makeFile(content: string, name = 'feeds.opml'): File {
  const f = new File([content], name, { type: 'text/xml' }) as FileWithText
  f.__testContent = content
  return f
}

function makeFileList(file: File): FileList {
  // jsdom doesn't expose DataTransfer, and `fireEvent.change` with a plain
  // `files: [file]` array makes `e.target.files?.[0]` undefined in some
  // versions. Build a minimal FileList-shaped object that satisfies the
  // page's `e.target.files?.[0]` read.
  const list = [file] as unknown as FileList
  ;(list as unknown as { item: (i: number) => File | null }).item = (i: number) =>
    list[i] ?? null
  return list
}

async function uploadFile(file: File) {
  const input = screen.getByTestId('opml-file') as HTMLInputElement
  fireEvent.change(input, { target: { files: makeFileList(file) } })
}

function renderImport(locale: 'en' | 'ru' = 'en') {
  return render(
    <IntlWrapper locale={locale}>
      <ImportPage />
    </IntlWrapper>
  )
}

describe('ImportPage (Task #35)', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the file picker initially and no preview', () => {
    renderImport()
    expect(screen.getByTestId('opml-file')).toBeInTheDocument()
    expect(screen.queryByTestId('submit-bulk')).not.toBeInTheDocument()
    expect(screen.queryByTestId('result-badges')).not.toBeInTheDocument()
  })

  it('parses a flat OPML file into 3 selectable feeds', async () => {
    renderImport()
    await uploadFile(makeFile(SAMPLE_OPML))

    // 3 feeds, all checked by default.
    const checkboxes = await screen.findAllByRole('checkbox')
    expect(checkboxes).toHaveLength(3)
    for (const cb of checkboxes) {
      expect((cb as HTMLInputElement).checked).toBe(true)
    }

    // Counter string.
    expect(screen.getByText(/3 of 3 selected/i)).toBeInTheDocument()
  })

  it('parses nested OPML and groups the child under its parent category badge', async () => {
    renderImport()
    await uploadFile(makeFile(SAMPLE_OPML))

    // Category header shows the full path (parent > child), not just the
    // parent — the page joins nested outline text attrs with " > ".
    const techHeader = await screen.findByText('Tech > GitHub Blog')
    expect(techHeader).toBeInTheDocument()

    // GitHub Blog feed is reachable; its aria-label uses the title.
    const githubAria = t_label_en('importCheckboxLabel', { title: 'GitHub Blog' })
    expect(await screen.findByLabelText(githubAria)).toBeInTheDocument()
  })

  it('rejects malformed XML with the importMalformed message and no preview', async () => {
    renderImport()
    await uploadFile(makeFile(MALFORMED_XML))

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(/malformed/i)
    })
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
    expect(screen.queryByTestId('submit-bulk')).not.toBeInTheDocument()
  })

  it('Select all / Deselect all toggles every checkbox', async () => {
    renderImport()
    await uploadFile(makeFile(SAMPLE_OPML))
    await screen.findAllByRole('checkbox')

    fireEvent.click(screen.getByRole('button', { name: 'Deselect all' }))
    for (const cb of screen.getAllByRole('checkbox')) {
      expect((cb as HTMLInputElement).checked).toBe(false)
    }
    expect(screen.getByText(/0 of 3 selected/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Select all' }))
    for (const cb of screen.getAllByRole('checkbox')) {
      expect((cb as HTMLInputElement).checked).toBe(true)
    }
    expect(screen.getByText(/3 of 3 selected/i)).toBeInTheDocument()
  })

  it('submit POSTs ONLY the selected subset (deselect 1 of 3 → body has 2)', async () => {
    const result: BulkImportResult = {
      created: 2,
      skipped_duplicates: 0,
      failed: [],
    }
    postMock.mockResolvedValueOnce(result)
    renderImport()
    await uploadFile(makeFile(SAMPLE_OPML))
    const checkboxes = await screen.findAllByRole('checkbox')

    // Deselect the first feed (Hacker News).
    fireEvent.click(checkboxes[0])
    expect((checkboxes[0] as HTMLInputElement).checked).toBe(false)

    fireEvent.click(screen.getByTestId('submit-bulk'))

    await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1))
    const [path, body] = postMock.mock.calls[0]
    expect(path).toBe('/feeds/bulk')
    const req = body as BulkImportRequest
    expect(req.feeds).toHaveLength(2)
    // Hacker News URL is gone; the other two remain.
    expect(req.feeds.map((f) => f.xmlUrl)).toEqual([
      'https://lobste.rs/rss',
      'https://github.blog/feed/',
    ])
    // category is stripped before POST (Architect flagged v1 discards it).
    for (const f of req.feeds) {
      expect(f.category).toBeUndefined()
    }
  })

  it('renders the success result: badges, failed list, and the link back to /feeds', async () => {
    const result: BulkImportResult = {
      created: 5,
      skipped_duplicates: 2,
      failed: [{ url: 'https://broken.example/rss', reason: 'Parse error' }],
    }
    postMock.mockResolvedValueOnce(result)

    renderImport()
    await uploadFile(makeFile(SAMPLE_OPML))
    const submit = await screen.findByTestId('submit-bulk')
    fireEvent.click(submit)

    await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1))
    const badges = await screen.findByTestId('result-badges')
    expect(badges).toBeInTheDocument()
    expect(screen.getByTestId('badge-created')).toHaveTextContent(/5 new feeds/)
    expect(screen.getByTestId('badge-duplicates')).toHaveTextContent(/2 duplicates/)
    expect(screen.getByTestId('badge-failed')).toHaveTextContent(/1 failed/)

    // Failed list with title and reason.
    const failedList = screen.getByTestId('failed-list')
    expect(failedList.textContent).toMatch(/Parse error/)

    // Link back to /feeds.
    const backLink = screen.getByRole('link', { name: /View your feeds/i })
    expect(backLink).toHaveAttribute('href', '/feeds')
  })

  it('surfaces ApiError.message on 4xx (e.g. over-limit)', async () => {
    postMock.mockRejectedValueOnce(
      new ApiError(422, 'Too many feeds (max 500). Try splitting the file.')
    )
    renderImport()
    await uploadFile(makeFile(SAMPLE_OPML))
    const submit = await screen.findByTestId('submit-bulk')
    fireEvent.click(submit)

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(/Too many feeds/)
    })
  })

  it('renders in Russian locale without throwing on missing keys', async () => {
    renderImport('ru')
    // Static UI text renders.
    expect(screen.getByText('Импорт лент из OPML')).toBeInTheDocument()
    expect(screen.getByText(/Загрузите OPML-файл/)).toBeInTheDocument()
    // After parsing, the Russian plural form is exercised. If any of the
    // `Feeds.import*` keys were missing, next-intl would render the key
    // path instead (e.g. "Feeds.importSelectedCount"), so the literal
    // string check below is a sufficient parity gate.
    await uploadFile(makeFile(SAMPLE_OPML))
    expect(await screen.findByText(/Выбрано 3 из 3/)).toBeInTheDocument()
  })
})

// Local helper — mirrors `useTranslations('Feeds').raw(...)` so the aria-label
// assertion above can be exact without re-implementing ICU pluralisation.
// Using a tiny standalone formatter keeps the test easy to follow.
function t_label_en(key: string, params: Record<string, string>): string {
  if (key === 'importCheckboxLabel') return `Subscribe to ${params.title}`
  return key
}
