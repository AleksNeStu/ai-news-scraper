# 📰 AI News Search

> Scrape, summarize, and semantically search your personal news library. FastAPI + Next.js 15 + ChromaDB monorepo.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black)](https://nextjs.org)
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
open http://localhost:3807
```

That's it — Postgres + Redis + ChromaDB + API + Web come up together. Register an account, scrape a URL, search.

> **Port matrix:** web=`3807`, api=`8007`, db=`5440`, redis=`6380`, chromadb=`8500` — see [`docs/ports.md`](./docs/ports.md) for the full table and the canonical source (the canonical port-registry file's `externalLocal.ai-news-scraper` entry).

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│  Next.js 15 (App Router)         localhost:3807 │
│  • /scrape   • /search   • /articles            │
│  • /feeds    • /settings • /login  • /register │
└────────────────┬────────────────────────────────┘
                 │  HTTP (JWT cookie)
                 ▼
┌─────────────────────────────────────────────────┐
│  FastAPI (Python 3.12+)         localhost:8007 │
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
└── web/          Next.js 15 frontend (port 3000)
packages/
└── shared/       TS types shared between api + web
docs/             Project documentation
.github/          CI workflows + community files
```

## ⚙️ Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind v4, shadcn/ui |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.x async, asyncpg |
| Vector DB | ChromaDB (persistent, metadata filtering) |
| RDB | Postgres 16 |
| Cache | Redis |
| Auth | JWT (httpOnly cookies) + bcrypt |
| AI | OpenAI (gpt-4o-mini + text-embedding-3-small) |
| RSS | feedparser + APScheduler |
| Workspace | pnpm + Poetry |

## 🔧 Development

### Local dev scripts (cross-platform)

The `scripts/dev/` directory wraps `docker compose` with healthcheck waits
and clear URLs — the same workflow on Linux, macOS, and Windows.

```bash
# Linux / macOS
bash scripts/dev/run.sh           # app stack
bash scripts/dev/run.sh --monitor # also Uptime Kuma
bash scripts/dev/run.sh --logs    # then tail logs (Ctrl-C to exit)
bash scripts/dev/stop.sh          # stop (--volumes to wipe data)
bash scripts/dev/logs.sh api      # tail one service
bash scripts/dev/status.sh        # one-shot snapshot

# Windows (PowerShell)
pwsh scripts/dev/run.ps1
pwsh scripts/dev/run.ps1 -Monitor
pwsh scripts/dev/run.ps1 -Logs
pwsh scripts/dev/stop.ps1
pwsh scripts/dev/logs.ps1 api
pwsh scripts/dev/status.ps1
```

All scripts print `http://localhost:3807` (web) and `http://localhost:8007`
(api) once the stack is healthy. The default dev login is
`alex@example.com` / `dev-only-do-not-use-in-prod` (seeded by the
one-shot `migrate` service).

### Bare docker compose

If you don't want the wrappers:

```bash
docker compose up -d
# then wait for healthchecks, open http://localhost:3807
```

### API only / Web only (no docker)

```bash
# API only
cd apps/api
poetry install
poetry run uvicorn api.main:app --reload

# Web only
cd apps/web
pnpm install
pnpm dev
```

### Tests & lint

```bash
# Tests
cd apps/api && poetry run pytest
cd apps/web && pnpm test

# Lint
cd apps/api && poetry run ruff check .
cd apps/web && pnpm lint && pnpm typecheck
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the PR process.

## 🚀 Production deploy

A first-time deployer should reach a healthy public URL in **under 30 minutes** using the steps below. The full per-var env schema, alembic/shell recipes, custom-domain setup, and the canonical smoke battery live in [`docs/operations/deploy.md`](docs/operations/deploy.md) — this section is the on-ramp.

### What runs where

| Service | Render resource | Plan | Notes |
|---|---|---|---|
| `web` (Next.js) | `type: web` (`ai-news-scraper-web`) | free | Renders the SPA and proxies `/api/backend/*` to the api origin. |
| `api` (FastAPI) | `type: web` (`ai-news-scraper-api`) | free | Owns the AI-Brief scheduler, scraping, semantic search, JWT issuance. |
| `postgres` | `databases:` (`ai-news-scraper-db`) | free | Managed — `DATABASE_URL` / `DATABASE_URL_SYNC` derive via `fromDatabase`. |

ChromaDB runs embedded as `PersistentClient` inside the api container (`/tmp/chroma`); the api's [`vector_store.py`](apps/api/api/services/vector_store.py) handles the no-server case automatically.

### Prerequisites

A first-time deploy needs all four. None are show-stoppers; they fall out of a free Render account + a clean repository clone.

- **Render account.** Free tier at <https://dashboard.render.com/>. No payment method required for the plan below.
- **Repo access.** Push access to the canonical `main` branch on the public GitHub repo. Render watches it via the GitHub integration and auto-deploys on every push.
- **DNS.** Default rollout lands on `https://<service-name>.onrender.com` — no DNS work needed. To attach a custom domain, add a CNAME (see `docs/operations/deploy.md` §5.3).
- **Outbound TCP 443** during build and runtime for: LLM provider APIs, SMTP (if `SMTP_HOST` is set), and package pulls during image build. Inbound TCP is handled at the Render edge.

### First-time deploy (step-by-step)

These are the five dashboard actions a deployer performs. After step 4 the stack is reachable.

1. **Sign in** at <https://dashboard.render.com/>.
2. **New + → Blueprint**. Point Render at the canonical repo on the `main` branch. Render reads [`render.yaml`](render.yaml) and provisions the three resources above.
3. **Fill the `sync: false` keys** in the per-service dashboard panels. These are the per-provider secrets:
   `REDIS_URL`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`,
   `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`,
   `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
   Empty defaults are valid for `REDIS_URL` and the SMTP block (degraded-mode behavior is documented below).
4. **`JWT_SECRET` and `UNSUBSCRIBE_JWT_SECRET`** are auto-minted at first provision because `render.yaml` declares them with `generateValue: true`. `DATABASE_URL` and `DATABASE_URL_SYNC` are auto-populated from the Postgres instance via `fromDatabase` — no entry needed in the dashboard.
5. **Click Manual Deploy** on each service for the first push. Render then auto-deploys on every push to `main`.

### Subsequent deploys

Push to `main`. Render builds the Docker images from the existing `apps/api/Dockerfile` and `apps/web/Dockerfile`, runs migrations via the api service's first-start hook (or via the dashboard Shell — see `docs/operations/deploy.md` §3), and rolls forward. Free-tier cold starts can take **30–60s after 15 minutes of inactivity**; bump client timeouts accordingly.

### Env vars (overview)

The full canonical schema is `[.env.example](.env.example)`; the per-key "where it lives on Render" mapping lives in `docs/operations/deploy.md` §2. The table below is the curated subset that a deployer should confirm is set in the dashboard. **Never commit real keys.**

| Variable | App | Required in prod | Render origin | Purpose |
|---|---|---|---|---|
| `APP_ENV` | api | yes | `value: production` | Toggles secure cookies + prod middleware. |
| `API_INTERNAL_URL` | api + web | yes | `value: https://ai-news-scraper-api.onrender.com` | Public api origin; web rewrite reads it at build time. |
| `DATABASE_URL` | api | yes | `fromDatabase` | asyncpg URL — see driver-prefix failure mode below. |
| `DATABASE_URL_SYNC` | api | yes | `fromDatabase` | Same for alembic migrations. |
| `JWT_SECRET` | api | **yes** | `generateValue: true` | HS256 signing key, 64+ random chars. |
| `UNSUBSCRIBE_JWT_SECRET` | api | yes (if digest email enabled) | `generateValue: true` | RFC 8058 signer — distinct from `JWT_SECRET`. |
| `CORS_ALLOW_ORIGINS` | api | yes | `value: ["https://ai-news-scraper-web.onrender.com"]` | Browser allowlist. |
| `CHROMA_PERSIST_DIR` | api | no | `value: /tmp/chroma` | Embedded `PersistentClient` path; ephemeral on free tier. |
| `REDIS_URL` | api | optional | `sync: false` | Rate-limit / digest cache. Empty = degraded mode. |
| `OPENAI_API_KEY` | api | for AI brief | `sync: false` | Placeholder `sk-replace-me` triggers degraded mode. |
| `LLM_PROVIDER` | api | no | `value: deepseek` | Multi-provider router (`deepseek` / `gemini` / `openrouter`). Per-provider key below. |
| `DEEPSEEK_API_KEY` | api | if `LLM_PROVIDER=deepseek` | `sync: false` | Provider key. |
| `SMTP_HOST` | api | for email digest | `sync: false` | Empty = email worker logs and bails; in-app delivery still works. |
| `PORT` | web | yes | `value: "10000"` | Render contract — container must listen on `$PORT`. |
| `NEXT_PUBLIC_API_URL` | web | yes | `value: /api/backend` | Same-origin relative proxy; survives TLS changes. |
| `NEXT_PUBLIC_APP_URL` | web | yes | `value: https://ai-news-scraper-web.onrender.com` | Public web origin. |

See `[.env.example](.env.example)` for the full list, and `docs/operations/deploy.md` §2 for which render.yaml mechanism (`value:`, `generateValue`, `sync: false`, `fromDatabase`) backs each key.

### Post-deploy health check

These three commands confirm the stack is healthy. They use the default `*.onrender.com` hostnames — substitute if a custom domain is attached.

```bash
# 1. Readiness probe (Postgres + Chroma per check).
curl -fsS https://ai-news-scraper-api.onrender.com/health
# Expect: {"status":"ok","env":"production","checks":{"postgres":"ok","chroma":"ok"}}

# 2. API docs (FastAPI Swagger).
curl -fsSI https://ai-news-scraper-api.onrender.com/docs | head -n1
# Expect: HTTP/2 200

# 3. Web homepage renders.
curl -fsSI https://ai-news-scraper-web.onrender.com | head -n1
# Expect: HTTP/2 200, then register/login in the browser.
```

A 503 from `/health` means one of the per-dependency checks failed — see Common failure modes below and inspect the api service logs in the Render dashboard.

### Rollback

Four options, ordered from fastest to deepest. Pick the lightest one that re-establishes a healthy state.

- **Dashboard rollback (fastest).** Service → **Events** → previous deploy → **Roll back to this deploy**. Render rebuilds and swaps in ~1–2 min; cold-start penalty still applies on free tier.
- **Git revert.** `git revert <bad-sha>` on `main`, push. Render auto-deploys the revert on the next hook tick.
- **Alembic downgrade.** If a bad release ran a migration, downgrade via the api service **Shell**:
  ```
  cd /app/apps/api
  poetry run alembic downgrade -1          # or: alembic downgrade <revision>
  ```
- **Database restore (last resort).** Render Postgres on free tier has automatic daily snapshots. Dashboard → `ai-news-scraper-db` → **Backups** → pick a snapshot → **Restore**. Full-instance replacement — do it last if other mitigation failed.

**Pre-deploy backup caveat:** Render Postgres free-tier backups are daily + 7-day retention; there is no point-in-time recovery. If durability matters, snapshot manually before a risky migration. ChromaDB at `/tmp/chroma` is ephemeral and not backed up — durable vector storage needs a paid tier with a persistent disk.

### Common failure modes

Each item below is a concrete symptom a deployer is likely to hit on first boot, with the fix in one line.

- **`DATABASE_URL` driver prefix.** SQLAlchemy errors at startup with "no async driver specified" because the `fromDatabase` value is a bare `postgresql://` URL. Override in the dashboard with `postgresql+asyncpg://...` (and `postgresql+psycopg2://...` for `DATABASE_URL_SYNC`). Cause + fix are documented in the `render.yaml` header.
- **ChromaDB ephemeral storage.** `/tmp/chroma` is wiped on every Render free-tier redeploy; the vector store loses all embeddings. Either re-run the ingest job or upgrade to a paid tier with a persistent disk.
- **`JWT_SECRET` placeholder leak (security-critical).** The default `change-me-in-production` declared at `apps/api/api/config.py:76` is **NOT rejected at runtime** — the api will happily sign and verify JWTs with the public default, which would let any reader of the open-source repo forge sessions for arbitrary users. The render.yaml `generateValue: true` is the only thing that keeps this safe in production. Confirm `JWT_SECRET` and `UNSUBSCRIBE_JWT_SECRET` resolved to real 64-char random strings in the dashboard (Environment → api service) **before the first request hits `/auth/login`**. If a deployer overrides the Blueprint and omits `generateValue: true`, the api ships with the public default secret — a critical incident.
- **Cold start 30–60s.** Free tier spins the service down after 15 minutes of idle time; the first request after that takes ~30–60s to wake up. If fast wake-up is required, upgrade to a paid tier or set up an external uptime-ping service that hits `/health` every 5 minutes.
- **Web build fails on `output: 'standalone'`.** `apps/web/next.config.ts` MUST have `output: 'standalone'` set, otherwise `next build` does not emit `.next/standalone` and the web container fails to COPY it (see `apps/web/next.config.ts:5–11` and `apps/web/Dockerfile:40`). The current `next.config.ts` already sets it; if a future change removes it, the build breaks.
- **`OPENAI_API_KEY=sk-replace-me` (degraded mode).** `/scrape` still works (falls back to NLTK extractive summaries) and the digest cron is silently disabled (per `apps/api/api/main.py` lifespan, lines 60–66). Set a real key in the dashboard to re-enable AI digest emails.
- **Missing `CORS_ALLOW_ORIGINS`.** Cross-origin browser calls fail silently because the api's CORS middleware rejects the origin. The render.yaml default already includes the web origin; only widen if a third-party client is added (OAuth, Slack bot, etc.).

### Cross-links

| Topic | File |
|---|---|
| Per-step runbook (full) | [`docs/operations/deploy.md`](docs/operations/deploy.md) |
| Env var schema (canonical) | [`.env.example`](.env.example) |
| Host ports + service ports | [`docs/ports.md`](docs/ports.md) |
| `/health` readiness contract | [`apps/api/api/routers/health.py`](apps/api/api/routers/health.py) |
| Deploy-target decision | internal ADR — full text is local-only and not committed to this public repo |
| Local dev (compose instead of Render) | **Quick Start** above (the same `docker-compose.yml` powers Render via the per-service Dockerfiles) |

## 📚 Documentation

| File | What |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Public contributing guide, PR process, commit convention |
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

The screenshots below are from the previous Streamlit UI (now removed). The new Next.js UI is at `localhost:3807` after `docker compose up`.

<div align="center">
  <img src="demo/1.png" alt="Application Home Screen" width="80%" />
  <p><em>Home screen</em></p>
</div>

## 🤝 Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). All contributions are licensed under [MIT](LICENSE).

## 📄 License

[MIT](LICENSE) — Copyright (c) 2026 AleksNeStu.
