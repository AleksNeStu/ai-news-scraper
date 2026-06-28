# AGENTS.md — AI Agent Guidance

> This file is **public** (tracked in repo) and applies to **any AI coding agent** working on this project (Claude Code, Cursor, Aider, Windsurf, etc.). For the project owner's personal agent notes, see the **private** `CLAUDE.md` at repo root — gitignored.

## Project pitch

**AI News Search** — a pnpm monorepo that scrapes news articles, summarizes + embeds them with LLMs, stores in Postgres + ChromaDB, and serves a Next.js 16 web UI for search, browsing, and RSS subscriptions. Public OSS-as-resume signal.

## Stack

```
apps/api/     FastAPI (Python 3.12+)    port 8082
apps/web/     Next.js 16 (App Router)   port 3000
packages/shared/  TS types shared between api and web
```

- DB: Postgres 16 (users / articles / feeds / feed_items)
- Vector: ChromaDB (replaces legacy FAISS)
- Cache: Redis
- Auth: JWT in HTTP-only cookies
- AI: OpenAI gpt-4o-mini + text-embedding-3-small (LangChain abstraction ready for Anthropic)
- RSS: feedparser + APScheduler
- Design: news/data-feel look — deep navy + electric cyan, Geist + Fraunces. See local `DESIGN.md` (private).

## Required reading

**Before writing any code, an agent must read:**

1. [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md) — hard rules, public/private boundary, git hygiene.
2. [`docs/PRD.md`](docs/PRD.md) — product requirements (legacy v2.0; canonical PRD is in `.agent/PRD.md`, private).
3. [`CONTRIBUTING.md`](CONTRIBUTING.md) — branch + commit + PR conventions.
4. `DESIGN.md` (private) — design tokens, anti-patterns. Ask owner to share if needed.

## Run / test / lint

```bash
# Full stack (Docker)
docker compose up -d
open http://localhost:3000

# API only
cd apps/api && poetry install && poetry run uvicorn api.main:app --reload

# Web only
cd apps/web && pnpm install && pnpm dev

# Tests
cd apps/api && poetry run pytest
cd apps/web && pnpm test

# Lint
cd apps/api && poetry run ruff check .
cd apps/web && pnpm lint && pnpm typecheck
```

## Hard rules (must follow)

Full detail in [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md). The agent-relevant subset:

- **Public/private boundary** — never propose committing anything from the PRIVATE scope (see table below).
- **No AI co-author lines** in commits.
- **No force-push to `main`**.
- **No GPL/AGPL packages**.
- **Conventional Commits** — `type(scope): description`, English only.
- **One logical change per commit**.
- **Branch from `dev`**, PR to `main`. No direct push to `main`.

## Public / private boundary

| Scope | Path | Tracked? | Why |
|---|---|---|---|
| **PUBLIC** | `apps/**`, `packages/**`, `docs/**`, `.github/**`, `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `SECURITY.md`, `CHANGELOG.md`, `LICENSE` | ✅ yes | visible to recruiters + contributors |
| **PRIVATE** | `.agent/**`, `CLAUDE.md`, `DESIGN.md`, `docs/research/**`, `.taskmaster/**`, `.claude/**`, `.roomodes`, `.windsurfrules`, `.cursor/**`, `.vscode/mcp.json` | ❌ gitignored | personal notes / AI tooling state |

When in doubt: would a recruiter or external contributor be confused by this file? If yes → PRIVATE.

## Workflow

1. Read PRD (`docs/PRD.md` or local `.agent/PRD.md` if shared).
2. Check task list via `mcp__mgmt-taskmaster__get_tasks` (local MCP — local workflow only).
3. Branch from `dev`: `git checkout -b feat/short-desc dev`.
4. Implement + test (pytest for api, vitest for web).
5. Lint (ruff for api, eslint + prettier for web).
6. Conventional commit.
7. Push to `main` remote `dev` branch (pre-push hook cascades to mirrors).
8. Open PR `dev → main` against `AleksNeStu/ai-news-scraper`.
9. Squash-merge when CI passes.

## Do NOT

- Commit secrets (API keys, tokens, passwords) — even in tests. Use `.env` (gitignored).
- Add `.agent/`, `CLAUDE.md`, `DESIGN.md`, `docs/research/` to the tracked set.
- Push directly to `main`.
- Force-push to `main`. Force-push to mirrors requires explicit owner approval.
- Modify `legacy/streamlit/` — that code is frozen for historical reference.
- Use the legacy Streamlit code as a starting point for new work — port logic into `apps/api/api/services/` instead.
- Skip the public/private boundary check in the PR template.
