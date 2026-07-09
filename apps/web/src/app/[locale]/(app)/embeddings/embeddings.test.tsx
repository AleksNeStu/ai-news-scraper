/**
 * Tests for the <EmbeddingsView /> client island (Task #34, ADR-022).
 *
 * Scope: prove the three user-visible guarantees the page delivers:
 *   1. Model picker fetches providers on mount and renders one row per
 *      provider.
 *   2. Disabled providers (those without `supports_embed` or without
 *      `key_configured`) render with `aria-disabled` + `disabled` and
 *      cannot be selected (clicking does NOT set them as the active
 *      provider; the Compute button stays disabled).
 *   3. The Compute button is disabled until BOTH textareas are non-empty.
 *
 * The page itself is a Server Component, which can't be rendered in
 * jsdom; the user-visible behaviour comes from this client island +
 * the VectorDisplay child (covered by its own test file).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { IntlWrapper } from '@/test-utils/intl-helper'
import { EmbeddingsView } from '@/app/[locale]/(app)/embeddings/EmbeddingsView'
import { computeSimilarity, listEmbeddingProviders } from '@/lib/api/embeddings'
import type { EmbeddingProvider, SimilarityResponse } from '@ai-news-scraper/shared'

vi.mock('@/lib/api/embeddings', () => ({
  listEmbeddingProviders: vi.fn(),
  computeSimilarity: vi.fn(),
  isProviderDoesNotSupportEmbedding: vi.fn(),
  isProviderKeyMissing: vi.fn(),
  isProviderUnknown: vi.fn(),
  embedText: vi.fn(),
}))

const listMock = vi.mocked(listEmbeddingProviders)
const similarityMock = vi.mocked(computeSimilarity)

const PROVIDERS: EmbeddingProvider[] = [
  {
    id: 'deepseek',
    display_name: 'DeepSeek',
    supports_embed: false, // disabled
    requires_own_key: true,
    key_configured: true,
    dimensions: null,
    default_model: null,
  },
  {
    id: 'gemini',
    display_name: 'Google Gemini',
    supports_embed: true,
    requires_own_key: true,
    key_configured: true,
    dimensions: 768,
    default_model: 'text-embedding-004',
  },
  {
    id: 'openrouter',
    display_name: 'OpenRouter',
    supports_embed: true,
    requires_own_key: true,
    key_configured: false, // disabled (no key)
    dimensions: 1536,
    default_model: 'openai/text-embedding-3-small',
  },
]

const SIM_RESPONSE: SimilarityResponse = {
  provider_id: 'gemini',
  model: 'text-embedding-004',
  dimensions: 768,
  vector_a: [0.1, 0.2, 0.3],
  vector_b: [0.4, 0.5, 0.6],
  cosine_similarity: 0.83,
}

function renderView() {
  return render(
    <IntlWrapper>
      <EmbeddingsView />
    </IntlWrapper>
  )
}

describe('<EmbeddingsView /> — provider picker (Task #34)', () => {
  beforeEach(() => {
    listMock.mockReset()
    similarityMock.mockReset()
    listMock.mockResolvedValue({ providers: PROVIDERS })
    similarityMock.mockResolvedValue(SIM_RESPONSE)
  })

  it('calls listEmbeddingProviders exactly once on mount', async () => {
    renderView()
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1))
  })

  it('renders one row per provider, with the right selectable flag', async () => {
    renderView()
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1))

    for (const p of PROVIDERS) {
      const row = await screen.findByTestId(`provider-${p.id}`)
      expect(row).toBeInTheDocument()
      const expectedSelectable = p.supports_embed && p.key_configured
      expect(row.getAttribute('data-selectable')).toBe(expectedSelectable ? 'true' : 'false')
      if (expectedSelectable) {
        expect(row.hasAttribute('disabled')).toBe(false)
        expect(row.getAttribute('aria-disabled')).toBe('false')
      } else {
        // Native disabled on a button also implies aria-disabled, so we
        // check the explicit attribute as well.
        expect(row.hasAttribute('disabled')).toBe(true)
        expect(row.getAttribute('aria-disabled')).toBe('true')
      }
    }
  })

  it('pre-selects the first selectable provider so the user can submit without an extra step', async () => {
    renderView()
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1))
    const gemini = await screen.findByTestId('provider-gemini')
    expect(gemini.getAttribute('aria-checked')).toBe('true')
    // disabled providers stay unchecked
    const deepseek = screen.getByTestId('provider-deepseek')
    expect(deepseek.getAttribute('aria-checked')).toBe('false')
  })

  it('does NOT change the active provider when a disabled row is clicked', async () => {
    renderView()
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1))

    // Try to click the disabled DeepSeek row.
    fireEvent.click(screen.getByTestId('provider-deepseek'))
    // The previously pre-selected Gemini should remain the active one.
    expect(screen.getByTestId('provider-gemini').getAttribute('aria-checked')).toBe('true')
    expect(screen.getByTestId('provider-deepseek').getAttribute('aria-checked')).toBe('false')

    // Same for the key-missing OpenRouter.
    fireEvent.click(screen.getByTestId('provider-openrouter'))
    expect(screen.getByTestId('provider-gemini').getAttribute('aria-checked')).toBe('true')
    expect(screen.getByTestId('provider-openrouter').getAttribute('aria-checked')).toBe('false')
  })
})

describe('<EmbeddingsView /> — submit gating', () => {
  beforeEach(() => {
    listMock.mockReset()
    similarityMock.mockReset()
    listMock.mockResolvedValue({ providers: PROVIDERS })
    similarityMock.mockResolvedValue(SIM_RESPONSE)
  })

  it('disables the Compute button when only one of the two textareas has text', async () => {
    renderView()
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1))
    const submit = await screen.findByTestId('submit-similarity')
    expect(submit.hasAttribute('disabled')).toBe(true)

    fireEvent.change(screen.getByTestId('text-a'), { target: { value: 'cat' } })
    expect(submit.hasAttribute('disabled')).toBe(true) // text B still empty

    fireEvent.change(screen.getByTestId('text-b'), { target: { value: 'kitten' } })
    expect(submit.hasAttribute('disabled')).toBe(false)
  })

  it('trims whitespace — whitespace-only inputs do not enable the button', async () => {
    renderView()
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1))
    const submit = await screen.findByTestId('submit-similarity')
    fireEvent.change(screen.getByTestId('text-a'), { target: { value: '   ' } })
    fireEvent.change(screen.getByTestId('text-b'), { target: { value: '   ' } })
    expect(submit.hasAttribute('disabled')).toBe(true)
  })

  it('calls computeSimilarity with the active provider + both texts and renders the cosine score', async () => {
    renderView()
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1))
    const submit = await screen.findByTestId('submit-similarity')

    fireEvent.change(screen.getByTestId('text-a'), { target: { value: 'cat' } })
    fireEvent.change(screen.getByTestId('text-b'), { target: { value: 'kitten' } })
    fireEvent.click(submit)

    await waitFor(() =>
      expect(similarityMock).toHaveBeenCalledWith({
        provider_id: 'gemini',
        text_a: 'cat',
        text_b: 'kitten',
      })
    )
    // Cosine score is rendered with the formatted value.
    await screen.findByTestId('cosine-score')
    expect(screen.getByTestId('cosine-score-value').textContent).toBe('0.8300')
    // The two vector panels are mounted.
    expect(screen.getByTestId('vector-a')).toBeInTheDocument()
    expect(screen.getByTestId('vector-b')).toBeInTheDocument()
  })
})
