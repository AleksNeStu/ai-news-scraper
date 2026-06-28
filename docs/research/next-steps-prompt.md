# Deep Research Prompt — AI News Search

> Hand this file (or its contents) to a future `/deep-research` skill invocation in a fresh session.
> Run order: `/deep-research` (single skill, ~3–5 min, 5+ sources).

## Project state

- **Repo**: `AleksNeStu/ai-news-scraper` — public, on GitHub profile.
- **Stack**: pnpm monorepo. `apps/api/` FastAPI (Python 3.12+) + `apps/web/` Next.js 16 (React 19, App Router, TS) + `packages/shared/`.
- **Data**: Postgres (users / articles / feeds / feed_items) + ChromaDB (vectors) + Redis (cache).
- **Auth**: JWT in HTTP-only cookies. bcrypt-hashed passwords.
- **AI**: OpenAI gpt-4o-mini (summary) + text-embedding-3-small (vectors). LangChain abstraction ready for Anthropic.
- **RSS**: feedparser + APScheduler (15-min poll).
- **Design**: news/data-feel look — deep navy + electric cyan accent. `DESIGN.md` is the source of truth.
- **Legacy**: `legacy/streamlit/` (frozen, deprecated).
- **Branching**: `dev` → `main` via PR per RepoALX matrix.

## What works (MVP)

- Scrape any URL → headline / body / summary / topics / vector in ≤30s.
- Semantic + hybrid search over user's article library.
- RSS subscriptions (CRUD + manual poll; auto-poll infrastructure not yet active).
- JWT auth — register / login / logout / me.
- Dashboard, scrape, search, articles (list + detail), feeds (list + add + delete + poll), settings.
- Docker compose for local dev (Postgres + Redis + ChromaDB + API + Web).

## Open gaps (from `docs/COMPREHENSIVE_TODO.md`)

- i18n (next-intl).
- Public shareable links.
- Embedding model playground.
- Slack / Discord / email delivery.
- Browser extension.
- Team workspaces.
- OAuth (Google / GitHub).
- Analytics dashboard (trends, top topics).
- Background scheduler (currently only manual poll).
- Kubernetes manifests.

## Target users

- **Research Analysts** — daily news digest + semantic recall across weeks of archives.
- **Content Managers** — RSS auto-import, curation, light analytics.
- **Developers / Data Scientists** — REST API, embedding playground, integration-friendly.

## Business posture

OSS-as-resume signal. **Primary objective**: GitHub profile relevance for backend / data-engineering / AI-engineering hiring managers + consulting clients. **Secondary** (acceptable but not central): GitHub Sponsors, Polar.sh tip jar.

## Goal of the research

Produce an evidence-backed report (5+ sources) answering:

1. **Audience growth mechanics.** Which channels produced highest ROI for comparable OSS news/RAG/AI-scraper projects in 2024–2026? (Show HN, /r/MachineLearning, Hugging Face Spaces, Replicate, GitHub Trending mechanics, Product Hunt, X / Twitter threads, dev.to, indiehackers, niche newsletters.)

2. **Feature roadmap impact.** From `docs/COMPREHENSIVE_TODO.md`, which 5–8 features would most move the needle for (a) external audience (stars / forks / mentions) and (b) inbound from potential clients (recruiters, founders, agencies)? Rank by effort vs. visibility.

3. **Pain-point closure.** Concrete pain points the target users actually voice publicly (Reddit, HN comments, G2 reviews of competitors: txtai, feedhive, newsapi, Exa, Perplexity, Feedly). Which does this project already partially solve?

4. **Distribution mechanics.** Specific tactics: README badge stack, social preview card, X / GitHub stars loops, OSS SEO (llms.txt, sitemap, structured data), changelog-driven growth, demo GIF, Vercel / Streamlit Cloud deployment, blog series on dev.to / personal site.

5. **Profile relevance signals.** What hiring managers / consulting clients actually look for in OSS profiles — commit cadence, issue responsiveness, doc quality, demo link, tests, CI badges. Concrete checklist.

6. **Monetization without breaking the OSS signal.** GitHub Sponsors, Polar.sh tip jar, hosted demo (Vercel), premium tier, content-curation API. Which fit the project's character?

## Output spec

- Save full report to `docs/research/next-steps-prompt-report.md` (Rule 95 canonical path).
- Print 1-page executive summary in chat.
- Include prioritized 30 / 60 / 90-day action plan.
- Cite every claim; show reasoning when sources disagree.
- ~10–15K tokens, ~3–5 min runtime.

## Copy-pastable prompt

```
/deep-research

You are researching growth, audience, and competitive positioning for an OSS project.

Repository: AleksNeStu/ai-news-scraper (public, on GitHub profile).
Stack: pnpm monorepo. apps/api (FastAPI, Python 3.12+) + apps/web (Next.js 16, React 19, App Router, TS) + packages/shared.
Database: Postgres + ChromaDB + Redis.
Auth: JWT in HTTP-only cookies.
AI: OpenAI gpt-4o-mini + text-embedding-3-small; LangChain abstraction ready for Anthropic.
RSS: feedparser + APScheduler (15-min poll).
Design: news/data-feel look — DESIGN.md is source of truth (deep navy + electric cyan).
Legacy: legacy/streamlit/ (frozen, deprecated).
Branching: dev → main via PR per RepoALX matrix.

What works (MVP): scrape any URL → summary + topics + vector in ≤30s. Semantic + hybrid search. RSS CRUD + manual poll (auto-poll infra not yet active). JWT auth (register/login/logout/me). Dashboard, scrape, search, articles (list + detail), feeds (list + add + delete + poll), settings. Docker compose for local dev.

Open gaps: i18n, public shareable links, embedding model playground, Slack/Discord/email delivery, browser extension, team workspaces, OAuth, analytics dashboard, background scheduler, Kubernetes manifests.

Target users:
- Research Analysts (daily news digest + semantic recall)
- Content Managers (RSS auto-import, curation, light analytics)
- Developers / Data Scientists (REST API, embedding playground, integration-friendly)

Business posture: OSS-as-resume signal. PRIMARY objective = GitHub profile relevance for backend / data-engineering / AI-engineering hiring managers and consulting clients. Secondary (acceptable but not central) = GitHub Sponsors, Polar.sh tip jar.

Goal: produce an evidence-backed report (5+ sources) answering:

1. Audience growth mechanics — which channels produced highest ROI for comparable OSS news/RAG/AI-scraper projects in 2024-2026? (Show HN, /r/MachineLearning, Hugging Face Spaces, Replicate, GitHub Trending mechanics, Product Hunt, X / Twitter threads, dev.to, indiehackers, niche newsletters.)

2. Feature roadmap impact — from COMPREHENSIVE_TODO, which 5-8 features would most move the needle for (a) external audience (stars/forks/mentions) and (b) inbound from potential clients (recruiters, founders, agencies)? Rank by effort vs visibility.

3. Pain-point closure — concrete pain points target users actually voice publicly (Reddit, HN, G2 reviews of competitors: txtai, feedhive, newsapi, Exa, Perplexity, Feedly). Which does this project already partially solve?

4. Distribution mechanics — specific tactics: README badge stack, social preview card, X/GitHub stars loops, OSS SEO (llms.txt, sitemap, structured data), changelog-driven growth, demo GIF, Vercel deployment, blog series on dev.to/personal site.

5. Profile relevance signals — what hiring managers / consulting clients actually look for in OSS profiles. Concrete checklist.

6. Monetization without breaking the OSS signal — GitHub Sponsors, Polar.sh tip jar, hosted demo, premium tier, content-curation API. Which fit?

Output:
- Save full report to docs/research/next-steps-prompt-report.md (canonical per Rule 95).
- Print 1-page executive summary in chat.
- Include prioritized 30 / 60 / 90-day action plan.
- Cite every claim; show reasoning when sources disagree.
- ~10–15K tokens, ~3–5 min runtime.
```