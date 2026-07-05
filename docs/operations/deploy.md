# Deploy runbook — AI News Scraper

Single-source-of-truth for shipping the stack to a fresh VPS via
`docker compose up`. Aligned with the Option A decision in
`.agent/adr/014-deploy-target.md` (full Dokploy, single compose project).

## 1. Pre-flight checklist

Before the first `docker compose up -d`:

| Item | Requirement |
|---|---|
| VPS | Linux x86_64; Ubuntu 22.04 LTS or 24.04 LTS recommended. 2 vCPU / 4 GB RAM minimum (Postgres + ChromaDB + API + Web + Redis = ~2.5 GB steady state; chromadb and the API can spike higher during scraping). |
| Disk | 40 GB minimum; 80 GB recommended. Fast SSD strongly preferred (ChromaDB random reads). |
| Inbound TCP | 80, 443 open from the public internet. 22 open to operator IP only (Dokploy agent outbound, not inbound). |
| Outbound TCP | 443 open (for Docker Hub pulls, OpenAI API, SMTP). No port restrictions needed by Postgres / Redis / Chroma — they're on the internal Docker network. |
| DNS | One A record pointing at the VPS IP, e.g. `app.<your-domain>`. Dokploy can also terminate TLS on the apex; either is fine. |
| TLS | Dokploy ships its own reverse proxy (Traefik); it provisions and auto-renews Let's Encrypt certs. No operator action needed at deploy time — point the domain at the VPS and tick "Request certificate" in the Dokploy UI for the compose project. |
| Dokploy agent | Installed on the host (per Dokploy docs). Only needed if Dokploy is the orchestrator; a raw `docker compose up -d` on the VPS works without it. |
| Public repo clone | `git clone git@github.com:AleksNeStu/ai-news-scraper.git /opt/ai-news-scraper` (or your fork). Switch to the `dev` branch for staging, `main` for production. |

## 2. Environment variables

The full surface lives in `.env.example`. Copy to `.env` and fill in real values:

```bash
cp .env.example .env
$EDITOR .env
```

The deploy-time Dokploy UI exposes the same keys; either place is canonical.
**Do not commit `.env`** — see `.gitignore`.

### 2.1 Vars consumed by the API

Every field declared on `Settings` in `apps/api/api/config.py:10-94` is
consumed by the FastAPI process. The subset below is the subset that
**must** be set for production. Vars listed in `.env.example` use the same
name; vars consumed by code but not in `.env.example` are listed here so
this runbook is the single source of truth.

| Name | Required in prod | Purpose | Consumed at | Example / default |
|---|---|---|---|---|
| `APP_ENV` | yes | Toggles `secure` cookie flag and any prod-only behaviour (currently only `secure` in `apps/api/api/routers/auth.py:42,67`). | `config.py:19` | `production` |
| `LOG_LEVEL` | no | Root-logger level. JSON formatter installed at startup (`api/middleware/logging.py:220`). | `config.py:20` | `INFO` |
| `API_HOST` | no | uvicorn bind. | `config.py:23` | `0.0.0.0` |
| `API_PORT` | no | uvicorn port. Matches `docker-compose.yml:107`. | `config.py:24` | `8082` |
| `API_INTERNAL_URL` | yes (compose) | Used by `docker-compose.yml` healthcheck. **Set to `http://api:8082`** inside the compose network; irrelevant to browser code. | `config.py:25` | `http://api:8082` |
| `DATABASE_URL` | yes | asyncpg URL. In compose: `postgresql+asyncpg://postgres:postgres@db:5432/ai_news`. | `config.py:28`, `alembic/env.py:44` | (see compose) |
| `DATABASE_URL_SYNC` | yes | psycopg2-style URL for tools. Same host/port/user/pw as above. | `config.py:31` | (see compose) |
| `CHROMA_HOST` | yes | In compose: `chromadb`. | `config.py:36`, `routers/health.py:81` | `chromadb` |
| `CHROMA_PORT` | yes | | `config.py:37`, `routers/health.py:82` | `8000` |
| `CHROMA_PERSIST_DIR` | no | Persistent vector dir when running outside compose. Compose uses the chromadb container's volume. | `config.py:38` | `./chroma_db` |
| `REDIS_URL` | yes | In compose: `redis://redis:6379/0`. | `config.py:41` | (see compose) |
| `OPENAI_API_KEY` | **CONDITIONAL** | Required for AI brief + scrape summarization. Without it, `/scrape` returns summaries in offline NLTK extractive mode (per PRD FR-2) and `DIGEST_ENABLED` quietly disables the cron (`main.py:51-56`). The placeholder `sk-replace-me` is detected and triggers a downgrade — set a real key or accept degraded mode. | `config.py:44`, `main.py:51` | real `sk-...` |
| `OPENAI_MODEL` | no | Chat model id. | `config.py:45` | `gpt-4o-mini` |
| `OPENAI_EMBEDDING_MODEL` | no | Embedding model id. | `config.py:46` | `text-embedding-3-small` |
| `ANTHROPIC_API_KEY` | no | Reserved by `Settings`; ADR-011 multi-provider route currently uses deepseek by default. | `config.py:47` | empty |
| `LLM_PROVIDER` | no | Per-provider router: `deepseek` / `gemini` / `openrouter` (ADR-011). | `config.py:53` | `deepseek` |
| `LLM_MODEL` | no | Override; provider default otherwise. | `config.py:54` | (empty) |
| `DEEPSEEK_API_KEY` | if `LLM_PROVIDER=deepseek` | ADR-011 provider key. | `config.py:55` | (empty) |
| `GEMINI_API_KEY` | if `LLM_PROVIDER=gemini` | | `config.py:56` | (empty) |
| `GOOGLE_API_KEY` | no | Mirror for Gemini key (TaskMaster config convention). | `config.py:57` | (empty) |
| `OPENROUTER_API_KEY` | if `LLM_PROVIDER=openrouter` | | `config.py:58` | (empty) |
| `EMBEDDING_DIMENSIONS` | no | Vector length; must match the model's output. | `config.py:59` | `1536` |
| `JWT_SECRET` | **yes** | HS256 signing key. The placeholder `change-me-in-production` is rejected silently — set a real long random string. **Use a 64-char random secret.** | `config.py:62`, `apps/api/api/services/auth.py` | `change-me-in-production` |
| `JWT_ALGORITHM` | no | JWT alg. | `config.py:63` | `HS256` |
| `JWT_EXPIRES_MIN` | no | JWT TTL. 1440 = 24h. | `config.py:64` | `1440` |
| `RSS_POLL_INTERVAL_SEC` | no | RSS polling cadence (PRD FR-7: 15 min). | `config.py:67` | `900` |
| `RSS_MAX_ITEMS_PER_POLL` | no | Cap per-feed. | `config.py:68` | `50` |
| `RSS_USER_AGENT` | no | feedparser User-Agent. | `config.py:69` | `ai-news-scraper/0.1` |
| `CORS_ALLOW_ORIGINS` | yes | List of web origins allowed to hit the API. In Option A (single host, Dokploy proxy), set to `[https://app.<your-domain>]`. Today defaults to `http://localhost:3000` — **change in prod or CORS will reject all browser calls**. | `config.py:72`, `main.py:88-95` | `["https://app.<your-domain>"]` |
| `SMTP_HOST` | if email brief wanted | Outbound SMTP for digest delivery. Empty = email worker logs and bails (`workers/email.py`). | `config.py:79` | (empty) |
| `SMTP_PORT` | if SMTP_HOST set | | `config.py:80` | `587` |
| `SMTP_USER` | if SMTP_HOST set | | `config.py:81` | (empty) |
| `SMTP_PASSWORD` | if SMTP_HOST set | | `config.py:82` | (empty) |
| `SMTP_FROM` | if SMTP_HOST set | Full from-address; falls back to `localhost` if malformed (`workers/email.py:116`). | `config.py:83` | (empty) |
| `DIGEST_ENABLED` | no | Primary kill switch for the AI-brief cron + router. Defaults `true`. Set `false` to disable digest completely. | `config.py:88`, `main.py:50` | `true` |
| `BRIEF_DISABLED` | no | Back-compat alias for `DIGEST_ENABLED`. | `config.py:89` | `false` |
| `UNSUBSCRIBE_JWT_SECRET` | **yes** (if digest email enabled) | RFC 8058 one-click unsubscribe JWT signer. Default empty → `/unsubscribe` 500s silently. **Set to a different random string from `JWT_SECRET`.** | `config.py:93`, `routers/digest.py` | (empty) |

### 2.2 Vars consumed by the Web

| Name | Required | Purpose | Consumed at | Example / default |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | yes | Public origin of the API as seen by the browser. Set to `https://app.<your-domain>/api/backend` so the rewrite in `apps/web/next.config.ts:18-21` proxies to the API over the same origin (Dokploy handles routing). | `apps/web/src/lib/api.ts:7` | `https://app.<your-domain>/api/backend` |
| `NEXT_PUBLIC_APP_URL` | yes | Public origin of the web app (reserved for future OG-tag / auth-redirect wiring — not yet consumed in the codebase). | (no consumer yet — declared in `.env.example`) | `https://app.<your-domain>` |
| `NEXT_PUBLIC_APP_NAME` | no | Display name in titles (reserved; consumed when OG / landing-page work lands). | (no consumer yet — declared in `.env.example`) | `"AI News Search"` |

### 2.3 Vars consumed by the `migrate` service only

| Name | Required | Purpose | Consumed at |
|---|---|---|---|
| `DATABASE_URL` | yes | The one-shot `migrate` service reuses this from the api env block (`docker-compose.yml:80`). |

## 3. Migration and seed order

Migrations run as a separate one-shot Docker service. Compose runs
`docker-compose.yml`'s services in dependency order; the `api` service
will not start until `migrate` exits 0 (`docker-compose.yml:101-102`):

```
migrate (depends_on: db:service_healthy)
  ├─ alembic upgrade head        # idempotent, no-op if already at head
  └─ python -m api.scripts.seed   # idempotent, every INSERT ON CONFLICT DO NOTHING

api (depends_on: migrate:service_completed_successfully)
web (depends_on: api)
```

The `seed.sql` file is **DEV ONLY**. Its committed bcrypt hash is for
the placeholder password `dev-only-do-not-use-in-prod` and the user
`alex@example.com`. A fresh prod deployment should:

1. Run `docker compose run --rm migrate alembic upgrade head` first.
2. Skip `python -m api.scripts.seed` entirely.
3. Create the first real user via `POST /auth/register` (see §4.2).

Operational sequence on a fresh VPS:

```bash
git pull origin dev            # or main for prod
docker compose pull
docker compose up -d db redis chromadb migrate   # wait for migrate to exit 0
docker compose up -d api web
docker compose ps              # confirm api + web are "Up" + healthy
```

The `migrate` service has `restart: "no"` (`docker-compose.yml:86`), so
re-running it requires an explicit `docker compose run --rm migrate ...`
invocation.

### Multiple replicas and migration races

Running more than one `api` replica is safe **after** `migrate` has
exited 0 (compose's `depends_on` + `service_completed_successfully`
gates all replicas on the same shared one-shot). For the first boot of
a fresh DB, do **not** start api replicas in parallel with a manual
`alembic upgrade head` — concurrent DDL on the same Postgres instance
will deadlock or fail. The one-shot `migrate` service is the
single-writer pattern that avoids this.

## 4. Smoke checks

All three checks below assume Dokploy routes `app.<your-domain>/api/backend/*`
to the API container, and `app.<your-domain>/` to the web container.

### 4.1 `/health` — readiness

```bash
curl -fsS https://app.<your-domain>/api/backend/health
```

Expect HTTP 200 with body:

```json
{
  "status": "ok",
  "env": "production",
  "checks": {"postgres": "ok", "chroma": "ok"}
}
```

If any check is `error: <ExceptionType>`, the corresponding dependency
is unreachable from the api container. Per ADR-008 §8.6, only the
exception class name is leaked. Inspect:

```bash
docker compose logs --tail=200 api
```

### 4.2 `/auth/register` — first user

```bash
curl -fsS -X POST https://app.<your-domain>/api/backend/auth/register \
  -H 'Content-Type: application/json' \
  -c /tmp/cookies.txt \
  -d '{"email":"you@example.com","password":"<long-random>"}'
```

Expect HTTP 201 with:

```json
{
  "user": {"id": "...", "email": "you@example.com"},
  "token": "<jwt>"
}
```

If you receive 409, the user already exists; use `/auth/login` instead.

### 4.3 `/scrape` — end-to-end pipeline

```bash
JWT=$(grep -o '"token":"[^"]*"' /tmp/cookies.txt | cut -d'"' -f4)

curl -fsS -X POST https://app.<your-domain>/api/backend/scrape \
  -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/your-test-article"}' \
  --max-time 30
```

Expect HTTP 201 with the `ArticleOut` JSON shape:
`{id, url, headline, summary, source_domain, publish_date, ...}`.
The PRD goal G1 ("scrape any URL → ... in ≤30s") requires the call to
complete within 30 seconds end-to-end. If it stalls, check
`docker compose logs --tail=100 api` for the request-id (look for the
`X-Request-ID` echoed on the 5xx response, or in the access log
`api.access: request completed path=/scrape status=... duration_ms=...`).

If you want a non-auth probe (e.g. for an external uptime monitor), use
`/health` (no auth) — see §4.1.

## 5. Rollback procedure

There is **no automated rollback path** in this compose project. Procedure
for an emergency revert is by hand:

```bash
# 1. Stop the active stack.
cd /opt/ai-news-scraper
docker compose down

# 2. Check out the last known-good commit.
git fetch origin main
git checkout <known-good-sha>

# 3. Rebuild only changed images (skip if you trust the cached image).
docker compose build

# 4. Redeploy.
docker compose up -d

# 5. If the bad release ran a database migration:
docker compose run --rm migrate alembic downgrade -1
# or for n-step downgrades:
docker compose run --rm migrate alembic downgrade <revision>
```

### Database snapshot restore

Postgres data lives in the `pgdata` named volume (`docker-compose.yml:30-31`).
Before every red-button rollback, snapshot the volume:

```bash
docker compose stop api
docker run --rm -v ai-news-scraper_pgdata:/from -v /tmp/backup:/to \
  alpine:3.20 sh -c 'cd /from && tar czf /to/pgdata-<timestamp>.tgz .'
docker compose start api
```

To restore from a snapshot:

```bash
docker compose down
docker run --rm -v ai-news-scraper_pgdata:/from -v /tmp/backup:/to \
  alpine:3.20 sh -c 'rm -rf /from/* && tar xzf /to/pgdata-<timestamp>.tgz -C /from'
docker compose up -d
docker compose run --rm migrate alembic upgrade head   # ensure schema is current
```

ChromaDB has no built-in snapshot format. Snapshot the `chromadata`
volume the same way; restore is identical. There is **no in-place
migration of vector data** — schema changes that touch embeddings
require a re-index job (out of scope for the MVP deploy).

## 6. Cross-links

| Topic | File |
|---|---|
| Env var schema (canonical) | `.env.example` |
| The stack itself | `docker-compose.yml` |
| API lifespan + middleware | `apps/api/api/main.py` |
| Pydantic Settings (where each var is read) | `apps/api/api/config.py:10-94` |
| Api image | `apps/api/Dockerfile` |
| Web image | `apps/web/Dockerfile` |
| CI gates (must pass before deploy) | `.github/workflows/ci.yml` |
| Local verification | `Makefile` (targets: `check`, `test-api`, `test-web`, `ci-local`) |
| Deploy target decision | `.agent/adr/014-deploy-target.md` |
| `/health` contract | `.agent/adr/008-health-endpoint-shape.md` |
| Logging posture | `.agent/adr/009-json-logging.md` |
| Exception / error posture | `.agent/adr/010-exception-hierarchy.md` |
| LLM provider routing | `.agent/adr/011-llm-provider-architecture.md` |
| Seed data (dev only) | `apps/api/scripts/seed.sql` + `apps/api/api/scripts/seed.py` |
| Migrations | `apps/api/alembic/` + `apps/api/alembic.ini` |
