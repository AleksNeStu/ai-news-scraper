/**
 * Tests for the ShareDialog client component (Task #33, ADR-021).
 *
 * Covers the user-visible flow on the article detail page:
 *   - Trigger button is rendered with the right accessible name.
 *   - Clicking the trigger POSTs to /share and shows the returned URL.
 *   - Clicking Copy writes the URL to navigator.clipboard.
 *
 * jsdom clipboard is missing by default; the test installs a
 * `mockResolvedValue('')` `writeText` spy on the same instance the
 * component will call.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ShareDialog } from '@/components/share/ShareDialog'
import { IntlWrapper } from '@/test-utils/intl-helper'
import * as shareApi from '@/lib/api/share'
import { ApiError } from '@/lib/api'
import type { ShareResponse } from '@ai-news-scraper/shared'

const FAKE_SHARE: ShareResponse = {
  token: 'tok-xyz',
  url: 'https://example.test/s/tok-xyz',
  expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
  article_id: 'art-1',
}

function renderDialog(articleId = 'art-1') {
  return render(
    <IntlWrapper>
      <ShareDialog articleId={articleId} headline="A news headline" />
    </IntlWrapper>
  )
}

describe('ShareDialog', () => {
  beforeEach(() => {
    // jsdom does not ship a clipboard implementation; install a stub.
    if (!('clipboard' in navigator)) {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: vi.fn().mockResolvedValue(undefined) },
        configurable: true,
      })
    } else {
      ;(navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mockReset?.()
      ;(navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mockResolvedValue(undefined)
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the trigger button with the accessible name from the Share namespace', () => {
    renderDialog()
    expect(screen.getByRole('button', { name: /share this article/i })).toBeInTheDocument()
  })

  it('POSTs to /share on open and shows the returned URL inside the dialog', async () => {
    const createSpy = vi.spyOn(shareApi, 'createShare').mockResolvedValueOnce(FAKE_SHARE)

    renderDialog('art-42')

    const trigger = screen.getByRole('button', { name: /share this article/i })
    fireEvent.click(trigger)

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith({ article_id: 'art-42', ttl_days: 30 })
    })
    const input = await screen.findByTestId('share-url-input')
    expect((input as HTMLInputElement).value).toBe(FAKE_SHARE.url)
  })

  it('writes the share URL to the clipboard when Copy is clicked', async () => {
    vi.spyOn(shareApi, 'createShare').mockResolvedValueOnce(FAKE_SHARE)
    const writeText = navigator.clipboard.writeText as ReturnType<typeof vi.fn>

    renderDialog()

    fireEvent.click(screen.getByRole('button', { name: /share this article/i }))

    const copyBtn = await screen.findByTestId('share-copy-button')
    fireEvent.click(copyBtn)

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(FAKE_SHARE.url)
    })
    await waitFor(() => {
      expect(screen.getByTestId('share-copy-confirmation').textContent).toMatch(/copied/i)
    })
  })

  it('renders an error message when POST /share fails', async () => {
    // ApiError is what `api.post` actually throws on a non-2xx response
    // (see apps/web/src/lib/api.ts); the component uses `e.message` for
    // ApiError and falls back to i18n copy only for non-ApiError throws.
    vi.spyOn(shareApi, 'createShare').mockRejectedValueOnce(
      new ApiError(500, 'Could not create share link')
    )

    renderDialog()

    fireEvent.click(screen.getByRole('button', { name: /share this article/i }))

    const err = await screen.findByTestId('share-error')
    expect(err.textContent).toContain('Could not create share link')
  })
})
