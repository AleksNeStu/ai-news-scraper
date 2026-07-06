# Deploy runbook — AI News Scraper

Single-source-of-truth for shipping the stack to production. The current
deploy target is **Render free tier** via Blueprint (`render.yaml`).
Local dev continues to use `docker-compose.yml` unchanged.

> **Render rollout uses the same `.env.example` schema as local dev**.
> Local reads env from disk via pydantic-settings; Render reads env from
> the dashboard's per-service entry, with `generateValue: true` /
> `fromDatabase` resolving the typed entries in `render.yaml`. There is
> no `.env.production` file at runtime.

## 1. Pre-flight checklist

Before the first Blueprint provision:

| Item | Requirement |
|---|---|
| Render account | Sign up at <https://dashboard.render.com/> (free tier). No payment method required for the free plan. |
| Repo access | Push access to the canonical `main` branch. Render watches it via GitHub integration. |
| DNS | The default rollout uses `https://<service-name>.onrender.com` — no DNS work needed. For a custom domain, add a CNAME in §5.3. |
| Inbound TCP | None — Render terminates public HTTPS at the edge. |
| Outbound TCP | 443 for HTTPS (LLM provider APIs, SMTP, package registries during build). |

### First-time deploy

1. Sign in at <https://dashboard.render.com/>.
2. **New +** → **Blueprint** → point at the canonical repo on the `main` branch.
3. Render parses `render.yaml` and provisions the Postgres database + two web services (`ai-news-scraper-api`, `ai-news-scraper-web`).
4. In the dashboard, fill the `sync: false` keys (`REDIS_URL`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ANTHROPIC_API_KEY`). `JWT_SECRET` and `UNSUBSCRIBE_JWT_SECRET` are auto-minted on first provision via `generateValue: true`. `DATABASE_URL` and `DATABASE_URL_SYNC` are auto-populated from the Postgres instance via `fromDatabase`.
5. Click **Manual Deploy** for the first push. Render then auto-deploys on every push to `main`.

### Subsequent deploys

Push to `main` from the canonical repo. Render builds the Docker images, runs migrations via the api service's first-start hook (or via the dashboard Shell), and rolls forward. Cold starts on the free tier can take ~30-60s after inactivity.

## 2. Environment variables

The canonical schema is `.env.example`. Each key's deploy-time origin
on Render is determined by `render.yaml`:

| Render mechanism | Meaning |
|---|---|
| `value:` | Literal baked into the Blueprint; override-able in dashboard. |
| `generateValue: true` | Render mints a random string at first provision. |
| `sync: false` | Operator sets in the dashboard; the Blueprint deliberately leaves it empty. |
| `fromDatabase:` | Pulled from the named Postgres instance's `connectionString`. |

### 2.1 Vars consumed by the API

Every field declared on `Settings` in `apps/api/api/config.py:10-94` is
consumed by the FastAPI process. The subset below is the subset that
**must** be set for production.

| Name | Required in prod | Render origin | Purpose |
|---|---|---|---|
| `APP_ENV` | yes | `value: production` | Toggles secure-cookie + prod-only middleware paths. |
| `LOG_LEVEL` | no | `value: INFO` | Root-logger level. |
| `API_HOST` | no | `value: 0.0.0.0` | uvicorn bind. |
| `API_PORT` | no | `value: "8082"` | uvicorn port. Matches `apps/api/Dockerfile`. |
| `API_INTERNAL_URL` | yes | `value: https://ai-news-scraper-api.onrender.com` | Public URL the api service exposes. Used by the web rewrite (`apps/web/next.config.ts:18-21`). |
| `DATABASE_URL` | yes | `fromDatabase` | asyncpg URL. Note: the `connectionString` value omits the `+asyncpg` driver prefix; if SQLAlchemy errors at startup with "no async driver specified", override with `postgresql+asyncpg://...` in the dashboard. |
| `DATABASE_URL_SYNC` | yes | `fromDatabase` | Same connectionString for alembic. Same driver-prefix caveat applies to psycopg2. |
| `CHROMA_HOST` | yes | `value: localhost` | Triggers the embedded `PersistentClient` path (`vector_store.py:53-59`). |
| `CHROMA_PORT` | no | `value: "8000"` | Legacy; unused in embedded mode. |
| `CHROMA_PERSIST_DIR` | no | `value: /tmp/chroma` | Ephemeral on Render free. Use a paid-tier persistent disk when durability matters. |
| `REDIS_URL` | yes (for rate-limit / digest) | `sync: false` | Operator-provided; Upstash free works. Empty default is fine for degraded mode. |
| `OPENAI_API_KEY` | conditional | `sync: false` | Required for AI brief + scrape summarization. Placeholder `sk-replace-me` detected by `apps/api/api/config.py:104-107` triggers degraded mode. |
| `OPENAI_MODEL` | no | `value: gpt-4o-mini` | Chat model id. |
| `OPENAI_EMBEDDING_MODEL` | no | `value: text-embedding-3-small` | Embedding model id. |
| `ANTHROPIC_API_KEY` | no | `sync: false` | Reserved by `Settings`; ADR-011 multi-provider route uses deepseek by default. |
| `LLM_PROVIDER` | no | `value: deepseek` | Per-provider router: `deepseek` / `gemini` / `openrouter`. |
| `LLM_MODEL` | no | `value: ""` | Override; provider default otherwise. |
| `DEEPSEEK_API_KEY` | if `LLM_PROVIDER=deepseek` | `sync: false` | Provider key. |
| `GEMINI_API_KEY` | if `LLM_PROVIDER=gemini` | `sync: false` | |
| `GOOGLE_API_KEY` | no | `sync: false` | Mirror for Gemini key. |
| `OPENROUTER_API_KEY` | if `LLM_PROVIDER=openrouter` | `sync: false` | |
| `EMBEDDING_DIMENSIONS` | no | `value: "1536"` | Vector length; must match model output. |
| `JWT_SECRET` | **yes** | `generateValue: true` | HS256 signing key. **64+ char random.** |
| `JWT_ALGORITHM` | no | `value: HS256` | JWT alg. |
| `JWT_EXPIRES_MIN` | no | `value: "1440"` | JWT TTL (24h). |
| `RSS_POLL_INTERVAL_SEC` | no | `value: "900"` | RSS polling cadence. |
| `RSS_MAX_ITEMS_PER_POLL` | no | `value: "50"` | Cap per-feed. |
| `RSS_USER_AGENT` | no | `value: ai-news-scraper/0.1` | feedparser UA. |
| `CORS_ALLOW_ORIGINS` | yes | `value: '["https://ai-news-scraper-web.onrender.com"]'` | List of allowed origins. Same-origin requests pass without a CORS check; cross-origin requires this allowlist. |
| `SMTP_HOST` | if email brief wanted | `sync: false` | Outbound SMTP. Empty = email worker logs and bails. |
| `SMTP_PORT` | if SMTP_HOST set | `value: "587"` | |
| `SMTP_USER` | if SMTP_HOST set | `sync: false` | |
| `SMTP_PASSWORD` | if SMTP_HOST set | `sync: false` | |
| `SMTP_FROM` | if SMTP_HOST set | `sync: false` | Full from-address. |
| `DIGEST_ENABLED` | no | `value: "true"` | Primary kill switch for AI-brief cron + router. |
| `BRIEF_DISABLED` | no | `value: "false"` | Back-compat alias. |
| `UNSUBSCRIBE_JWT_SECRET` | **yes** (if digest email enabled) | `generateValue: true` | RFC 8058 one-click unsubscribe signer. **Different from JWT_SECRET.** |

### 2.2 Vars consumed by the Web

| Name | Required | Render origin | Purpose |
|---|---|---|---|
| `PORT` | yes (Render contract) | `value: "10000"` | Render web-service contract: container must listen on `$PORT`. |
| `HOSTNAME` | yes | `value: 0.0.0.0` | `next start` bind address. |
| `NODE_ENV` | yes | `value: production` | Sets `process.env.NODE_ENV` for cookie `secure` flag etc. |
| `NEXT_TELEMETRY_DISABLED` | no | `value: "1"` | Suppresses Next.js telemetry. |
| `API_INTERNAL_URL` | yes | `value: https://ai-news-scraper-api.onrender.com` | Server-side rewrite destination (`apps/web/next.config.ts:18-21`). |
| `NEXT_PUBLIC_API_URL` | yes | `value: /api/backend` | Relative path = same-origin proxy via Next.js rewrite. |
| `NEXT_PUBLIC_APP_URL` | yes | `value: https://ai-news-scraper-web.onrender.com` | Public origin of the web app. |
| `NEXT_PUBLIC_APP_NAME` | no | `value: "AI News Scraper"` | Display name in titles. |

## 3. Migration and seed order

There is no separate "migrate" service on Render. The first deploy runs
`alembic upgrade head` from the api service's Shell:

1. Render dashboard → `ai-news-scraper-api` → **Shell** tab.
2. Run:
   ```
   cd /app/apps/api
   poetry run alembic upgrade head
   ```
3. (Optional) seed a dev user:
   ```
   poetry run python -m api.scripts.seed
   ```
   For prod, skip this — create the first real user via `/auth/register`
   (§4.4).

### Multiple replicas and migration races

Render free runs a single instance per service, so there is no
cross-replica DDL race. If you scale up, run `alembic upgrade head` once
from the Shell before the new replicas take traffic.

## 4. Smoke checks

The URLs in this section assume the default `*.onrender.com` hostnames.
If a custom domain is attached (see §5.3), substitute it.

### 4.1 `/health` — readiness

```bash
curl -fsS https://ai-news-scraper-web.onrender.com/api/backend/health
```

(The browser fetches the web origin; the Next.js rewrite at
`apps/web/next.config.ts:18-21` proxies to the api origin. From the
terminal, the same path is followed by `next start`.)

Expect HTTP 200 with:

```json
{
  "status": "ok",
  "env": "production",
  "checks": {"postgres": "ok", "chroma": "ok"}
}
```

`chroma` reports via the embedded `PersistentClient` path
(`apps/api/api/routers/health.py:71-93`). If it ever reports `error`:
inspect the api service logs in the dashboard.

### 4.2 TLS / HSTS

```bash
curl -fsSI https://ai-news-scraper-web.onrender.com/api/backend/health \
  | grep -i strict-transport-security
```

Expect a `max-age=...` line. Render auto-provisions the cert; HSTS is
additive from `apps/api/api/middleware/security_headers.py:84-87` when
`app_env == "production"`.

### 4.3 CORS preflight (cross-service)

```bash
curl -fsSI -X OPTIONS https://ai-news-scraper-api.onrender.com/auth/login \
  -H 'Origin: https://ai-news-scraper-web.onrender.com' \
  -H 'Access-Control-Request-Method: POST' \
  | grep -i access-control-allow-origin
```

Expect `https://ai-news-scraper-web.onrender.com` echoed back.

### 4.4 First user — `/auth/register`

```bash
curl -fsS -X POST https://ai-news-scraper-web.onrender.com/api/backend/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"<long-random>"}'
```

Expect HTTP 201 with `{user, token}`. If 409, the user exists — use
`/auth/login` instead.

### 4.5 End-to-end — `/scrape`

```bash
JWT=$(curl -fsS -X POST https://ai-news-scraper-web.onrender.com/api/backend/auth/login \
        -H 'Content-Type: application/json' \
        -d '{"email":"you@example.com","password":"<long-random>"}' \
      | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')

curl -fsS -X POST https://ai-news-scraper-web.onrender.com/api/backend/scrape \
  -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/your-test-article"}' \
  --max-time 30
```

Expect an `ArticleOut`-shaped JSON. Cold start can add ~30-60s on the
free tier; bump `--max-time` if needed.

### 4.6 One-shot smoke battery — `make smoke-e2e`

For the canonical G1 acceptance battery (Task #24), `scripts/smoke-e2e.sh`
chains the four steps above plus a `/search` recall assertion in one
run:

```bash
BASE_URL=https://ai-news-scraper-web.onrender.com make smoke-e2e
# Default: one URL + paraphrase pair (Wikipedia: Cloud computing).
# Pass --full (via the script) to cycle through three pairs.
BASE_URL=https://ai-news-scraper-web.onrender.com bash scripts/smoke-e2e.sh --full
```

The script requires `jq`, `curl`, and the `openssl` CLI on PATH. It
asserts `summary.length ∈ [100, 600]` (PRD range 100-300 with NLTK-fallback
tolerance for long pages) and that the scraped article surfaces in the
top-3 of `/search` results for a paraphrase. The recall assertion will
fail without an LLM provider key in the dashboard — the script prints a
hint when `/search` returns zero results.

## 5. Rollback procedure

There is no automated rollback path on Render. To revert a bad release:

### 5.1 App rollback

1. Dashboard → `ai-news-scraper-api` (and `-web`) → **Manual Deploy** → pick a prior commit SHA from the dropdown.
2. Render rebuilds and swaps. Cold start ~30-60s on the free tier.

### 5.2 Database rollback

1. If the bad release ran a migration, downgrade via the api service Shell:
   ```
   cd /app/apps/api
   poetry run alembic downgrade -1
   # or for an explicit revision:
   poetry run alembic downgrade <revision>
   ```
2. Postgres data lives in the managed `ai-news-scraper-db` instance.
   Render takes automatic daily snapshots (7-day retention on free).
   Restore via dashboard → `ai-news-scraper-db` → **Backups** → pick a snapshot → **Restore**. This is a full-instance replacement; do it last if other mitigation failed.

### 5.3 Custom domain

1. In the DNS provider, add a CNAME: `<your-subdomain>` → `ai-news-scraper-web.onrender.com`.
2. Render dashboard → `ai-news-scraper-web` → **Settings** → **Custom Domains** → **Add** → enter `<your-subdomain>`.
3. Render provisions a Let's Encrypt cert automatically. Repeat for the api service if `api.<your-domain>` is wanted.
4. After cert is active, update `NEXT_PUBLIC_APP_URL` in render.yaml (or via dashboard) and `CORS_ALLOW_ORIGINS` to the new origins.

### 5.4 ChromaDB rollback

`/tmp/chroma` is ephemeral; the vector index resets on the next
container restart. Re-index after rollback if semantic search matters
(run a one-shot backfill job — out of scope for the MVP deploy).

## 6. Cross-links

| Topic | File |
|---|---|
| Env var schema (canonical) | `.env.example` |
| Blueprint definition | `render.yaml` |
| Compose stack (local dev) | `docker-compose.yml` |
| API lifespan + middleware | `apps/api/api/main.py` |
| Pydantic Settings (where each var is read) | `apps/api/api/config.py:10-94` |
| Vector store + chromadb fallback | `apps/api/api/services/vector_store.py` |
| Health probe (Postgres + Chroma) | `apps/api/api/routers/health.py` |
| HSTS / security headers | `apps/api/api/middleware/security_headers.py` |
| Next.js rewrite (browser → api) | `apps/web/next.config.ts:18-21` |
| API client fetch helper | `apps/web/src/lib/api.ts` |
| Api image | `apps/api/Dockerfile` |
| Web image | `apps/web/Dockerfile` |
| CI gates (must pass before deploy) | `.github/workflows/ci.yml` |
| Local verification | `Makefile` (targets: `check`, `test-api`, `test-web`, `ci-local`, `render-validate`) |
| Deploy target decision | `.agent/adr/014-deploy-target.md` |
| `/health` contract | `.agent/adr/008-health-endpoint-shape.md` |
| Logging posture | `.agent/adr/009-json-logging.md` |
| Exception / error posture | `.agent/adr/010-exception-hierarchy.md` |
| LLM provider routing | `.agent/adr/011-llm-provider-architecture.md` |
| Seed data (dev only) | `apps/api/scripts/seed.sql` + `apps/api/api/scripts/seed.py` |
| Migrations | `apps/api/alembic/` + `apps/api/alembic.ini` |
