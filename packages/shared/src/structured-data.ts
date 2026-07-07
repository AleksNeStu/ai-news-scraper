/**
 * Structured data contracts for GEO readiness.
 *
 * Two exports live in this module:
 *
 * (A) JSON-LD TypeScript interfaces — strictly the fields we emit, all
 *     serializable (no `Date`, no `undefined` in field types, no
 *     functions). Schema.org reference: https://schema.org/.
 *
 * (B) A canonical `llms.txt` builder that follows the 4-rule format
 *     published by Answer.AI and adopted across ChatGPT, Claude,
 *     Perplexity, and Google-Extended crawlers (spec: llmstxt.com).
 *
 * The builder is locale-agnostic: it accepts a `resolvePath` callback
 * so this package stays free of app-level i18n imports. The web app
 * injects `@/i18n/navigation.getPathname` + `routing.locales` at the
 * call site.
 *
 * IMPORTANT: The link allowlist at the bottom of this file is the
 * single source of truth for which routes llms.txt advertises. Adding
 * or removing a public route means editing `LLMS_ROUTE_SECTIONS`
 * below — never a directory walk (Devil pre-flight review).
 */

// ============================================================================
// (A) JSON-LD schema interfaces
// ============================================================================

/** Common envelope shared by every top-level JSON-LD node. */
export interface WithContext<T extends string> {
  '@context': 'https://schema.org';
  '@type': T;
  /** Optional canonical identifier (IRI). */
  '@id'?: string;
}

export interface Organization extends WithContext<'Organization'> {
  name: string;
  url: string;
  /** Absolute URL to a square logo (recommended 112x112 or larger). */
  logo?: string;
  /** Social/profile URLs (Twitter, GitHub, LinkedIn, etc.). */
  sameAs?: string[];
  description?: string;
}

export interface WebSite extends WithContext<'WebSite'> {
  name: string;
  url: string;
  /** BCP-47 language tag (e.g. `en`, `ru`). */
  inLanguage: string;
  potentialAction?: SearchAction;
}

export interface SearchAction {
  '@type': 'SearchAction';
  target: {
    '@type': 'EntryPoint';
    /** URL template with `{search_term_string}` placeholder. */
    urlTemplate: string;
  };
  /** Schema.org query-input convention: `"required name=search_term_string"`. */
  'query-input': string;
}

export interface Offer {
  '@type': 'Offer';
  /** Price as a string (preserves currency formatting; `"0"` for free). */
  price: string;
  /** ISO 4217 currency code (e.g. `USD`, `EUR`). */
  priceCurrency: string;
}

export interface SoftwareApplication extends WithContext<'SoftwareApplication'> {
  name: string;
  url: string;
  /** Schema.org category (e.g. `BusinessApplication`, `DeveloperApplication`). */
  applicationCategory: string;
  /** Comma-separated OS list or a single OS name. */
  operatingSystem?: string;
  description?: string;
  offers?: Offer;
}

export interface ArticleJsonLd extends WithContext<'Article'> {
  /** Article headline (recommended ≤ 110 chars). */
  headline: string;
  /** ISO 8601 publication timestamp. */
  datePublished: string;
  /** ISO 8601 last-modified timestamp. */
  dateModified?: string;
  /** Author display name (plain string, not a Person object — keeps
   *  the contract minimal; rich authorship lives elsewhere). */
  author?: string;
  /** Absolute URL to a representative image. */
  image?: string;
  /** Canonical URL of the article page. */
  mainEntityOfPage: string;
  /** BCP-47 language tag. */
  inLanguage: string;
  description?: string;
  /** Comma-separated keywords. */
  keywords?: string;
}

export interface BreadcrumbItem {
  '@type': 'ListItem';
  /** 1-based ordinal position in the trail. */
  position: number;
  /** Display name of the crumb. */
  name: string;
  /** Absolute URL of the crumb target. */
  item: string;
}

export interface BreadcrumbList extends WithContext<'BreadcrumbList'> {
  itemListElement: BreadcrumbItem[];
}

export interface CollectionPage extends WithContext<'CollectionPage'> {
  name: string;
  url: string;
  description?: string;
  /** BCP-47 language tag. */
  inLanguage: string;
}

/** Discriminated union of every top-level node this project emits. */
export type StructuredDataNode =
  | Organization
  | WebSite
  | SoftwareApplication
  | ArticleJsonLd
  | BreadcrumbList
  | CollectionPage;

// ============================================================================
// (B) Canonical llms.txt builder
// ============================================================================

/** A single bulleted entry inside a `## Section` block. */
export interface LlmsLink {
  /** Display title for the link (also used as anchor text). */
  title: string;
  /** Absolute URL — built at call time via `opts.resolvePath` +
   *  `opts.siteUrl`. The allowlist stores `path` only. */
  url: string;
  /** Optional one-line description rendered after the colon. */
  description?: string;
}

/** A `## Section` block in the llms.txt document. */
export interface LlmsSection {
  /** Section heading rendered as `## <heading>`. */
  heading: string;
  /** Bulleted links in display order. */
  links: LlmsLink[];
}

/** Top-level inputs the builder needs to emit a document. */
export interface LlmsDocInput {
  /** Project name (rendered as the `# <name>` title). */
  name: string;
  /** One-paragraph project summary (rendered as the blockquote). */
  summary: string;
  /** Ordered sections. */
  sections: LlmsSection[];
}

/** Locales the builder emits per route. Mirrors `routing.locales` in
 *  the web app; kept inline here so the shared package has no app deps.
 *  When the web app adds a third locale, extend this union and the
 *  allowlist constant in tandem. */
export type LlmsLocale = 'en' | 'ru';

/** Resolves a locale-tagged, app-internal path into a final absolute
 *  path component. The web app injects `getPathname` from
 *  `@/i18n/navigation`; the architect's builder stays locale-agnostic
 *  so this package never imports from `apps/web/**` or
 *  `apps/api/**`. */
export type LlmsPathResolver = (input: {
  locale: LlmsLocale;
  path: string;
}) => string;

/** Builder options injected by the caller. */
export interface LlmsBuildOptions {
  /** Bare origin (no trailing slash), e.g. `https://example.com`. */
  siteUrl: string;
  /** Locale-aware path resolver (see `LlmsPathResolver`). */
  resolvePath: LlmsPathResolver;
}

// ----------------------------------------------------------------------------
// Explicit route allowlist (single source of truth).
// ----------------------------------------------------------------------------
//
// Keep this list aligned with `apps/web/src/app/sitemap.ts` (the public
// route surface). When a route is added to or removed from the app,
// edit THIS file — not a directory walk.
//
// Internal routes (`/api/*`, `(auth)` group, anything under
// `/dashboard/*` that requires a session) MUST NOT appear here.
// AI crawlers reading this file are unauthenticated; advertising
// auth-only URLs would be misleading at best and a soft-privsec leak
// at worst.

interface AllowedLink {
  title: string;
  /** Internal path WITHOUT locale prefix; `resolvePath` adds it. */
  path: string;
  description?: string;
}

interface AllowedSection {
  /** Section heading. Emitted once per locale as `## <heading> (en)` /
   *  `## <heading> (ru)`. */
  heading: string;
  links: readonly AllowedLink[];
}

/**
 * Routes the llms.txt file advertises. Update this when adding or
 * removing a public route. Internal/auth-only routes MUST NOT appear.
 */
const LLMS_ROUTE_SECTIONS: readonly AllowedSection[] = [
  {
    heading: 'Main pages',
    links: [
      { title: 'Home', path: '/', description: 'Project landing page and live overview.' },
      { title: 'Articles', path: '/articles', description: 'Browse the full indexed article corpus.' },
      { title: 'Search', path: '/search', description: 'Semantic + keyword search across articles.' },
      { title: 'Dashboard', path: '/dashboard', description: 'Per-user activity and curation overview.' },
      { title: 'AI Brief', path: '/dashboard/brief', description: 'Daily digest of clustered, scored articles.' },
      { title: 'RSS Feeds', path: '/feeds', description: 'Manage RSS / Atom feed subscriptions.' },
      { title: 'Scrape', path: '/scrape', description: 'Submit URLs for one-off scraping and summarization.' },
      { title: 'Settings', path: '/settings', description: 'Account, notifications, and digest preferences.' },
      { title: 'Login', path: '/login', description: 'Sign in to an existing account.' },
      { title: 'Register', path: '/register', description: 'Create a new account.' },
      { title: 'Unsubscribe', path: '/unsubscribe', description: 'One-click digest unsubscribe (RFC 8058).' },
    ],
  },
  {
    heading: 'API endpoints',
    links: [
      { title: 'POST /scrape', path: '/api/scrape', description: 'Scrape and summarize one or more URLs.' },
      { title: 'POST /search', path: '/api/search', description: 'Search indexed articles by semantic similarity.' },
      { title: 'GET /articles', path: '/api/articles', description: 'List and paginate indexed articles.' },
      { title: 'GET /health', path: '/api/health', description: 'Service health and readiness probe.' },
    ],
  },
];

/** Locales to emit per route. Kept in this file (rather than imported
 *  from app-level i18n) so the shared package has zero app deps. */
const LLMS_LOCALES: readonly LlmsLocale[] = ['en', 'ru'];

// ----------------------------------------------------------------------------
// Builder
// ----------------------------------------------------------------------------

/**
 * Render a single bulleted link line. Internal; exported only via the
 * main builder. Returns one `- [Title](url): description` line.
 */
function formatLinkLine(link: LlmsLink): string {
  const base = `- [${link.title}](${link.url})`;
  return link.description ? `${base}: ${link.description}` : base;
}

/**
 * Render one section heading. Locale-suffixed so AI crawlers that
 * parse the file linearly can map each block to a locale without
 * having to guess path prefixes (which differ per locale under
 * `localePrefix: 'as-needed'`).
 */
function formatSectionHeading(heading: string, locale: LlmsLocale): string {
  return `## ${heading} (${locale})`;
}

/**
 * Build a full llms.txt document from `input` using `opts` to resolve
 * paths. Pure function — no I/O, no clock, no globals. Same inputs
 * always produce the same output.
 */
export function buildLlmsTxt(
  input: LlmsDocInput,
  opts: LlmsBuildOptions,
): string {
  const { name, summary, sections } = input;
  const { siteUrl, resolvePath } = opts;

  const lines: string[] = [];

  // 4-rule format: title, blockquote summary, optional detail line.
  lines.push(`# ${name}`);
  lines.push('');
  lines.push(`> ${summary}`);
  lines.push('');

  // If the caller passed custom sections, emit them first (using the
  // raw links the caller supplied — the allowlist is the *default*
  // surface, but the builder is a general-purpose tool).
  for (const section of sections) {
    for (const locale of LLMS_LOCALES) {
      lines.push(formatSectionHeading(section.heading, locale));
      for (const link of section.links) {
        lines.push(formatLinkLine(link));
      }
      lines.push('');
    }
  }

  // Then the explicit allowlist, expanded per locale with locale-aware
  // path resolution and the configured site origin.
  for (const section of LLMS_ROUTE_SECTIONS) {
    for (const locale of LLMS_LOCALES) {
      lines.push(formatSectionHeading(section.heading, locale));
      for (const allowed of section.links) {
        const absolutePath = resolvePath({ locale, path: allowed.path });
        const link: LlmsLink = {
          title: allowed.title,
          url: `${siteUrl}${absolutePath}`,
          ...(allowed.description !== undefined
            ? { description: allowed.description }
            : {}),
        };
        lines.push(formatLinkLine(link));
      }
      lines.push('');
    }
  }

  // Trim the trailing blank line so callers can append a trailing
  // newline themselves if they want a POSIX-style file terminator.
  while (lines.length > 0 && lines[lines.length - 1] === '') {
    lines.pop();
  }
  return lines.join('\n');
}
