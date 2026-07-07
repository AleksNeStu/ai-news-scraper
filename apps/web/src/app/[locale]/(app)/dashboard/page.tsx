/**
 * /dashboard — top-pick hero + per-tier curated sections (Task #32).
 *
 * Server Component. Reads the latest must_read / recommended / worth_a_look
 * articles via `listArticles({ tier, pageSize })` (Task #9 backend filter).
 * Each call uses `next: { revalidate: 300 }` for a 5-minute cache so a
 * handful of dashboard hits per minute don't hammer Postgres/Redis.
 *
 * The dashboard is intentionally a *reading* surface: empty states are
 * surfaced in user-facing copy, never thrown.
 *
 * i18n (Task #32):
 *   - Tier labels come from `getTranslations('Tiers')` — collapses the
 *     prior `TIER_HEADINGS` map into the message catalog (single source
 *     of truth). The dashboard's `mustReadSection` label stays in the
 *     `Dashboard` namespace because the hero band uses slightly
 *     different copy ("Must Read" → localized via `Tiers.mustRead` would
 *     read "Обязательно к прочтению"; the hero wants the section
 *     heading style, hence the dedicated key).
 *   - `formatRelative` takes the active locale.
 */

import { getTranslations, setRequestLocale } from 'next-intl/server'
import type { Metadata } from 'next'
import { Link, getPathname } from '@/i18n/navigation'
import { listArticles, topInTier } from '@/lib/api/articles'
import { formatRelative } from '@/lib/utils'
import { ScoreRing } from '@/components/ScoreRing'
import { StructuredData } from '@/components/StructuredData'
import { SITE_URL } from '@/lib/site'
import { buildSoftwareApplicationJsonLd, SITE_DESCRIPTION } from '@/lib/structured-data/builders'
import type { Article, Tier } from '@ai-news-scraper/shared'

const HERO_LIMIT = 3
const SECTION_LIMIT = 5

export const revalidate = 300

type Fetched = Awaited<ReturnType<typeof listArticles>>
async function safeFetch(opts: Parameters<typeof listArticles>[0]): Promise<Fetched> {
  return listArticles(opts).catch(() => ({ items: [], total: 0, page: 1, page_size: 0 }))
}

/**
 * Page metadata (Task #28): canonical + og:* + twitter:*. Reuses the
 * /dashboard path across both locales via `getPathname` so the absolute
 * URL respects `localePrefix: 'as-needed'`.
 */
export async function generateMetadata({
  params,
}: {
  params: { locale: string }
}): Promise<Metadata> {
  const { locale } = params
  const path = '/dashboard'
  const canonical = `${SITE_URL}${getPathname({ locale: locale as 'en' | 'ru', href: path })}`
  return {
    title: 'Dashboard',
    description: SITE_DESCRIPTION,
    alternates: { canonical },
    openGraph: {
      title: 'Dashboard',
      description: SITE_DESCRIPTION,
      type: 'website',
      url: canonical,
      siteName: 'ai-news-scraper',
      locale: locale === 'en' ? 'en_US' : 'ru_RU',
    },
    twitter: {
      card: 'summary_large_image',
      title: 'Dashboard',
      description: SITE_DESCRIPTION,
    },
  }
}

export default async function DashboardPage({ params }: { params: { locale: string } }) {
  const { locale } = params
  setRequestLocale(locale)
  const t = await getTranslations('Dashboard')
  const tTiers = await getTranslations('Tiers')

  // Three independent fetches — all hit the same backend endpoint with
  // different `tier` filters. Server Components await in parallel by default.
  const [must_read, recommended, worth_a_look] = await Promise.all([
    safeFetch({ tier: 'must_read', pageSize: HERO_LIMIT }),
    safeFetch({ tier: 'recommended', pageSize: SECTION_LIMIT }),
    safeFetch({ tier: 'worth_a_look', pageSize: SECTION_LIMIT }),
  ])

  const hero = must_read.items.slice(0, HERO_LIMIT)
  const recommendedList = topInTier(recommended.items, 'recommended', SECTION_LIMIT)
  const worthALookList = topInTier(worth_a_look.items, 'worth_a_look', SECTION_LIMIT)

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      {/* GEO readiness (Task #28): SoftwareApplication JSON-LD surfaces
          the app + dashboard as a first-class schema.org entity. */}
      <StructuredData data={buildSoftwareApplicationJsonLd()} />
      <header className="mb-8">
        <h1 className="text-3xl font-semibold headline-serif">{t('topPicksHeading')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t('topPicksSubheading')}</p>
      </header>

      {hero.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-8 text-center">
          <h2 className="font-medium">{t('mustReadEmpty.title')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t('mustReadEmpty.body')}</p>
        </div>
      ) : (
        <section aria-labelledby="hero-heading" className="mb-10">
          <h2
            id="hero-heading"
            className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground"
          >
            {t('mustReadSection')}
          </h2>
          <div className="grid gap-4 md:grid-cols-3">
            {hero.map((a) => (
              <HeroCard key={a.id} article={a} cta={t('readCta')} />
            ))}
          </div>
        </section>
      )}

      {recommendedList.length > 0 && (
        <TierSection
          tier="recommended"
          items={recommendedList}
          label={tTiers('recommended')}
          locale={locale}
        />
      )}
      {worthALookList.length > 0 && (
        <TierSection
          tier="worth_a_look"
          items={worthALookList}
          label={tTiers('worthALook')}
          locale={locale}
        />
      )}
    </main>
  )
}

function HeroCard({ article, cta }: { article: Article; cta: string }) {
  return (
    <Link
      href={`/articles/${article.id}`}
      className="flex flex-col gap-3 rounded-lg border border-border bg-canvas p-5 transition hover:border-primary/40"
    >
      <div className="flex items-center gap-3">
        <ScoreRing score={article.score} tier={article.tier} size="md" showLabel />
        <span className="text-xs text-muted-foreground">{article.source_domain}</span>
      </div>
      <h3 className="headline-serif text-lg">{article.headline ?? article.url}</h3>
      {article.summary && (
        <p className="line-clamp-2 text-sm text-muted-foreground">{article.summary}</p>
      )}
      <span className="mt-auto text-xs text-primary">{cta}</span>
    </Link>
  )
}

function TierSection({
  tier,
  items,
  label,
  locale,
}: {
  tier: Tier
  items: Article[]
  label: string
  locale: string
}) {
  return (
    <section aria-labelledby={`section-${tier}`} className="mb-10">
      <header className="mb-3 flex items-baseline justify-between">
        <h2 id={`section-${tier}`} className="text-lg font-semibold headline-serif">
          {label}
        </h2>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {items.length}
        </span>
      </header>
      <ul className="space-y-3">
        {items.map((a) => (
          <li key={a.id}>
            <Link
              href={`/articles/${a.id}`}
              className="flex items-start gap-4 rounded-lg border border-border bg-canvas p-4 transition hover:border-primary/40"
            >
              <div className="pt-1">
                <ScoreRing score={a.score} size="sm" tier={a.tier} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="headline-serif text-base line-clamp-1">{a.headline ?? a.url}</h3>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatRelative(a.indexed_at, locale)}
                  </span>
                </div>
                {a.summary && (
                  <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{a.summary}</p>
                )}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
