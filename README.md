# 📰 AI News Search

> Scrape, summarize, and semantically search your personal news library. FastAPI + Next.js 16 + ChromaDB monorepo.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python%203.12-009688)](https://fastapi.tiangolo.com)
[![ChromaDB](https://img.shields.io/badge/vector-ChromaDB-orange)](https://www.trychroma.com)

---

## What is this?

AI News Search is a **personal semantic news library**:

- **Scrape** any URL → headline, body, AI summary (100–300 words), topics, vector embedding.
- **Semantic search** across your private article library — "what did I read 3 weeks ago about AI regulation?" returns relevant results by meaning, not keyword.
- **RSS subscriptions** with auto-polling (15-min cadence).
- **JWT auth** — your library stays yours.
- **Public OSS** — MIT license, this repo doubles as a portfolio signal.

See [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md) for the public/private boundary policy.

## 🚀 Quick Start

```bash
git clone https://github.com/AleksNeStu/ai-news-scraper.git
cd ai-news-scraper

cp .env.example .env
# edit .env — set OPENAI_API_KEY (required) + JWT_SECRET (any long random string)

docker compose up -d
open http://localhost:3000
```

That's it — Postgres + Redis + ChromaDB + API + Web come up together. Register an account, scrape a URL, search.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│  Next.js 16 (App Router)         localhost:3000 │
│  • /scrape   • /search   • /articles            │
│  • /feeds    • /settings • /login  • /register │
└────────────────┬────────────────────────────────┘
                 │  HTTP (JWT cookie)
                 ▼
┌─────────────────────────────────────────────────┐
│  FastAPI (Python 3.12+)         localhost:8082 │
│  /scrape  /articles  /search  /feeds  /auth    │
│  → ChromaVectorStore  → Postgres (async)       │
│  → OpenAI gpt-4o-mini + text-embedding-3-small  │
│  → Redis cache (5-min search TTL)               │
└─────────────────────────────────────────────────┘
```

Monorepo layout:

```
apps/
├── api/          FastAPI backend (port 8082)
└── web/          Next.js 16 frontend (port 3000)
packages/
└── shared/       TS types shared between api + web
docs/             Project documentation
.github/          CI workflows + community files
```

## ⚙️ Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind v4, shadcn/ui |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.x async, asyncpg |
| Vector DB | ChromaDB (persistent, metadata filtering) |
| RDB | Postgres 16 |
| Cache | Redis |
| Auth | JWT (httpOnly cookies) + bcrypt |
| AI | OpenAI (gpt-4o-mini + text-embedding-3-small) |
| RSS | feedparser + APScheduler |
| Workspace | pnpm + Poetry |

## 🔧 Development

```bash
# API only
cd apps/api
poetry install
poetry run uvicorn api.main:app --reload

# Web only
cd apps/web
pnpm install
pnpm dev

# Tests
cd apps/api && poetry run pytest
cd apps/web && pnpm test

# Lint
cd apps/api && poetry run ruff check .
cd apps/web && pnpm lint && pnpm typecheck
```

See [`AGENTS.md`](AGENTS.md) for agent-specific guidance and [`CONTRIBUTING.md`](CONTRIBUTING.md) for the PR process.

## 📚 Documentation

| File | What |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Public contributing guide, PR process, commit convention |
| [`AGENTS.md`](AGENTS.md) | AI agent guidance (Claude Code, Cursor, Aider, etc.) |
| [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md) | **Hard rules** — public/private boundary, git hygiene, branch discipline |
| [`docs/PRD.md`](docs/PRD.md) | Product requirements (legacy v2.0) |
| [`docs/CI-CD.md`](docs/CI-CD.md) | CI/CD documentation |
| [`docs/TASKMASTER_GUIDE.md`](docs/TASKMASTER_GUIDE.md) | TaskMaster workflow guide |
| [`docs/TASK_MANAGEMENT.md`](docs/TASK_MANAGEMENT.md) | Task tracking |
| [`docs/COMPREHENSIVE_TODO.md`](docs/COMPREHENSIVE_TODO.md) | Roadmap (open gaps) |
| [`docs/COMPETITIVE_ANALYSIS.md`](docs/COMPETITIVE_ANALYSIS.md) | Competitive landscape |
| [`SECURITY.md`](SECURITY.md) | Security disclosure policy |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history |
| [`LICENSE`](LICENSE) | MIT License |

## 🎯 Target users

- **Research Analysts** — daily news digest + semantic recall across weeks of archives.
- **Content Managers** — RSS auto-import, curation, light analytics.
- **Developers / Data Scientists** — REST API, embedding playground, integration-friendly.

## 📸 Demo (legacy Streamlit UI)

The screenshots below are from the previous Streamlit UI (now removed). The new Next.js UI is at `localhost:3000` after `docker compose up`.

<div align="center">
  <img src="demo/1.png" alt="Application Home Screen" width="80%" />
  <p><em>Home screen</em></p>
</div>

## 🤝 Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). All contributions are licensed under [MIT](LICENSE).

## 📄 License

[MIT](LICENSE) — Copyright (c) 2026 AleksNeStu.