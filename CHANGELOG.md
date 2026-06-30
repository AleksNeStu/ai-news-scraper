# Changelog

All notable changes to **AI News Search** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Pre-release note (2026-06-30)

The current `main` is tagged **`v0.1.0-pre`** to mark the monorepo
as **pre-release** despite the `[0.1.0] - 2026-06-28` entry below
calling it v0.1.0. Reasoning: the CHANGELOG entry was written before
the migration was complete. The actual public v0.1.0 will be tagged
when:

- Web UI feature set matches the PRD
- All 3 CI jobs green on `main` (achieved 2026-06-30)
- The 4 pre-existing test failures are resolved (achieved 2026-06-30)

All three gates are now met, so a follow-up release is imminent.
Track progress on the [Releases page](https://github.com/AleksNeStu/ai-news-scraper/releases).

The previous Stacklit + flat-structure era is preserved on the
`legacy/streamlit` branch and tagged `v0.0.0-streamlit-final`. See
README → Releases for the table.

## [Unreleased]

### Added
- **Public project rules** — `CONTRIBUTING.md`, `AGENTS.md`, `docs/PROJECT_RULES.md` (canonical public/private boundary policy).
- **Community files** — `SECURITY.md` (responsible disclosure), `CHANGELOG.md`, `LICENSE` (MIT), `.github/CODE_OF_CONDUCT.md` (Contributor Covenant v2.1), `.github/pull_request_template.md` (with public/private boundary checkbox), `.github/FUNDING.yml` (GitHub Sponsors placeholder), `.github/CODEOWNERS` (`@AleksNeStu` for all paths).

### Planned
- Background RSS scheduler (APScheduler wired into FastAPI lifespan).
- Bulk article import via OPML.
- Public shareable article links.

## [0.1.0] - 2026-06-28

Initial public monorepo release.

### Added
- **Monorepo scaffold** — pnpm workspaces with `apps/api` (FastAPI), `apps/web` (Next.js 16), `packages/shared` (TS types).
- **Backend** (`apps/api/`) — FastAPI app with 5 routers (auth, articles, scrape, search, feeds), 4 SQLAlchemy models (User, Article, Feed, FeedItem), 6 services (scraper, summarizer, embedder, vector_store, feed_parser, auth), JWT auth in HTTP-only cookies.
- **Frontend** (`apps/web/`) — Next.js 16 (App Router, React 19, TypeScript) with shadcn/ui (re-themed), Tailwind v4 with custom news/data-feel palette (deep navy + electric cyan + amber warn), 7 pages (dashboard, scrape, search, articles, feeds, settings, login/register).
- **Vector store** — ChromaDB replaces legacy FAISS (persistent, supports metadata filtering).
- **Database** — Postgres schema for users, articles, feeds, feed_items.
- **Auth** — bcrypt password hashing + JWT issue/verify, cookie-based session.
- **AI** — OpenAI gpt-4o-mini (summary) + text-embedding-3-small (vectors), LangChain abstraction ready for Anthropic.
- **RSS** — feedparser for parsing, manual poll endpoint ready.
- **Docker compose** — multi-service stack (db + redis + chromadb + api + web).
- **CI** — GitHub Actions for api (lint + test) + web (build + typecheck + lint).
- **Dependabot** — weekly security updates for pip, npm, GitHub Actions.
- **Documentation** — `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `SECURITY.md`, `docs/PROJECT_RULES.md`, `docs/PRD.md`, `docs/CI-CD.md`, `docs/COMPREHENSIVE_TODO.md`, `docs/COMPETITIVE_ANALYSIS.md`, `docs/TASKMASTER_GUIDE.md`, `docs/TASK_MANAGEMENT.md`.
- **License** — MIT.
- **Push matrix** — 3 remotes (`AleksNeStu` canonical + `dev-scaler` + `nest-ai-dev` mirrors), pre-push hook cascades automatically.

### Changed
- **Vector DB** — FAISS → ChromaDB (persistent, queryable metadata).
- **Frontend stack** — Streamlit (Python) → Next.js 16 (TypeScript).
- **Project structure** — flat → monorepo (`apps/*` + `packages/*`).

### Deprecated
- **Streamlit UI** — moved to `legacy/streamlit/`. Frozen, not maintained. Do not extend.

### Removed
- **Legacy stack fully purged** (post-v0.1.0): `legacy/streamlit/`, root `Dockerfile`, `requirements.txt`, `cli.py`, `urls.txt`, `.gitlab-ci.yml`, `azure-pipelines.yml`, old `tests/`, `scripts/` (Streamlit runners + Azure DevOps setup).
- README rewritten for the new monorepo (no more Streamlit/CLI references).

### Security
- All `.env*` files (except `.env.example`) gitignored.
- All AI / IDE tooling state (`.claude/`, `.roomodes`, `.windsurfrules`, `.cursor/`, `.vscode/mcp.json`, `.taskmaster/`) gitignored.
- `.agent/` (PRD, ADRs) and root `CLAUDE.md` and `DESIGN.md` kept local-only.
- See `docs/PROJECT_RULES.md` for the full public/private boundary policy.
