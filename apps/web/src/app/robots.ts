/**
 * /robots.txt — Next.js metadata route (Task #28 Frontend half).
 *
 * Two-tier ruleset:
 *   1. The default `*` user-agent is allowed everywhere — the app has
 *      no auth-only public surface that should be hidden from generic
 *      crawlers. Private routes (auth-required) are gated at render
 *      time by the middleware; robots.txt cannot enforce that.
 *   2. Each well-known AI crawler gets an explicit `allow: '/'` entry.
 *      This is symbolic (they would have crawled `/` by default under
 *      rule 1) but documents intent: the project is a public resource
 *      and we do not block AI ingestion of its content. Spec references
 *      for each bot:
 *        - GPTBot          → OpenAI's crawler (cited by ChatGPT search)
 *        - ClaudeBot       → Anthropic's autonomous crawler
 *        - Claude-User     → Anthropic's user-triggered fetch agent
 *                            (distinct from ClaudeBot — invoked when a
 *                            Claude user explicitly asks it to fetch a
 *                            URL; both ship today, both allowed)
 *        - PerplexityBot   → Perplexity's crawler
 *        - Google-Extended → Google's AI-training opt-in flag
 *        - Applebot-Extended → Apple's AI-training opt-in flag
 *
 * `sitemap` and `host` are emitted as absolute URLs so search engines
 * can verify the canonical site origin in a single fetch.
 *
 * Pattern reference: `apps/web/src/lib/site.ts` — the same `SITE_URL`
 * origin is used so the three routes (sitemap, robots, llms.txt)
 * never disagree on the canonical host.
 */

import type { MetadataRoute } from 'next'
import { SITE_URL } from '@/lib/site'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: '*', allow: '/' },
      { userAgent: 'GPTBot', allow: '/' },
      { userAgent: 'ClaudeBot', allow: '/' },
      { userAgent: 'Claude-User', allow: '/' },
      { userAgent: 'PerplexityBot', allow: '/' },
      { userAgent: 'Google-Extended', allow: '/' },
      { userAgent: 'Applebot-Extended', allow: '/' },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  }
}
