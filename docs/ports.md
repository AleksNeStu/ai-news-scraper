# Port Matrix — ai-news-scraper

> **Source of truth:** `E:\nestlab-repo\nest-solo\docs\architecture\PORT_REGISTRY.json`
> **Canonical entry:** `externalLocal.ai-news-scraper` (v2.4.0, 2026-07-08).
> **Rule reference:** `E:\nestlab-repo\nest-solo\docs\architecture\port-management.md`.

This document is the **local mirror** of the ai-news-scraper entry in
nest-solo's `PORT_REGISTRY.json`. If you change a port here, change the
registry too (and vice-versa). The two are intentionally duplicated —
the registry is canonical for collision-checking across the whole
nest-solo ecosystem, this file is the on-disk pointer for ai-news-scraper
contributors.

---

## Range conventions (per nest-solo)

| Resource  | Range         | Increment rule | Source         |
| --------- | ------------- | -------------- | -------------- |
| Frontend  | `3800-3899`   | +1 per product | `port-management.md` §"Folder-based Port Ranges" |
| Backend   | `8000-8099`   | +1 per product | same           |
| Database  | `5433-5499`   | +1 per product | same (5432 reserved for shared `nestlab-dev-postgres`) |
| Redis     | `6300-6499`   | per-product    | `port-management.md` |
| ChromaDB  | no formal range (high ports, `8500+`) | n/a     | this repo      |

`8082` is **reserved for `propvectorai`** (see registry entry). `ai-news-scraper`'s
backend sits in the next free slot at `8007` to avoid that collision.

---

## ai-news-scraper — local dev allocation

| Service       | Container port | Host port | Notes |
| ------------- | -------------- | --------- | ----- |
| **web**       | `3000` (Next.js default) | **`3807`** | Browser: `http://localhost:3807`. Replaces the previous default `:3000`. |
| **api**       | `8000` (uvicorn default) | **`8007`** | Browser: `http://localhost:8007`. Swagger at `/docs`. Replaces the previous `:8082` (which clashed with `propvectorai`). |
| **database**  | `5432` (Postgres default) | **`5440`** | Dev-only; `pgdata` named volume persists across restarts. Replaces shared `5432`. |
| **redis**     | `6379` (Redis default) | **`6380`** | Dev-only isolated Redis; replaces shared `6379`. `redisdata` named volume. |
| **chromadb**  | `8000` (ChromaDB HTTP) | **`8500`** | Replaces previous `:8000` which clashed with `checkcv.backend=8000`. `chromadata` named volume. |

---

## Where these numbers live in code

| File                                               | What it sets                                  |
| -------------------------------------------------- | --------------------------------------------- |
| `docker-compose.yml`                               | `ports:` mappings (host side); `API_INTERNAL_URL: http://api:8000`; `NEXT_PUBLIC_API_URL: http://localhost:8007`; `API_PORT: "8000"`; healthcheck URLs. |
| `apps/api/api/config.py`                           | `api_port: int = 8000`, `api_internal_url: str = "http://localhost:8000"`. |
| `apps/api/Dockerfile`                              | `EXPOSE 8000`, `CMD uvicorn --port 8000`, `HEALTHCHECK ... localhost:8000/health`. |
| `apps/web/Dockerfile`                              | `ARG API_INTERNAL_URL=http://api:8000` (consumed at build time by `next.config.ts`). |
| `.env.example`                                     | `API_PORT=8000`, `API_INTERNAL_URL=http://api:8000`. |
| `scripts/dev/{run,stop,logs,status}.ps1` (and `.sh`) | Healthcheck polling + the URL block printed in `run.ps1`. |
| `CLAUDE.md` §"Run / test / lint"                   | Documents the canonical host ports in the Quick Start snippet. |

---

## Why the previous ports were broken

The original allocation (web `:3000`, api `:8082`, db `:5432`, redis `:6379`,
chromadb `:8000`) collided with at least three other products:

| Old host port | Collided with                                           |
| ------------- | ------------------------------------------------------- |
| `8082` (api)  | `propvectorai.backend` (`PORT_REGISTRY.json` v2.x) + `ai-real-estate-assistant`'s `docker-compose.quick.yml:8082:8000` |
| `8000` (chromadb) | `checkcv.backend` (`PORT_REGISTRY.json` v.x)        |
| `3000` (web)  | Standard Next.js default (out of the 3800-3899 range)  |
| `5432` (db)   | shared `nestlab-dev-postgres`                          |
| `6379` (redis)| shared `nestlab-dev-redis`                             |

After the fix the only reserved/canonical port used by ai-news-scraper is
**5432 inside containers** (Postgres) and **6379 inside containers**
(Redis) — the compose host-side mappings put everything in the canonical
3800+ / 8000+ ranges.

---

## Related products' ports (per `externalLocal`)

| Product                          | Frontend | Backend  | Database | Other        |
| -------------------------------- | -------- | -------- | -------- | ------------ |
| `E:\repo\repo-alex\cv`            | `3001`   | `8001`   | n/a      | n/a          |
| `E:\repo\repo-alex\ai-real-estate-assistant` (quick compose) | `???` | `8082` ⚠️ | n/a | ⚠️ frozen repo — see note |
| `E:\repo\repo-alex\ai-news-scraper` (this repo) | **`3807`** | **`8007`** | **`5440`** | redis `6380`, chroma `8500` |

⚠️ `ai-real-estate-assistant`'s `docker-compose.quick.yml:8082:8000` is
**out of sync** with its registry allocation of `8004`. Per project
policy the ai-real-estate-assistant repo is **frozen** (public demo,
no further changes — see `E:\repo\repo-alex\ai-real-estate-assistant\CLAUDE.md`).
The mismatch between its compose and the registry is therefore
**accepted as-is** and **must not** be auto-fixed from nest-solo or
from ai-news-scraper. New nest-solo products continue to avoid the
`8082` slot for that reason.

---

## When you change a port

1. Update the code files in `docker-compose.yml`, `apps/api/api/config.py`,
   `apps/api/Dockerfile`, `apps/web/Dockerfile`, `.env.example`,
   `scripts/dev/{run,status}.ps1`, `CLAUDE.md`.
2. Bump the version in `E:\nestlab-repo\nest-solo\docs\architecture\PORT_REGISTRY.json`
   (the registry is canonical; semver: +0.0.1 if additive only) and add
   a `changelog` entry.
3. Mirror the change here in `docs/ports.md` (this file).
4. Run `bash E:/nestlab-repo/nest-solo/local/scripts/portfolio/shared/show-ports.ps1`
   to check no other registered product now collides.
5. Tear down and bring the stack back up with `pwsh scripts/dev/{stop,run}.ps1`
   so the new host ports take effect.

**Do NOT** touch `ai-real-estate-assistant` (E:\repo\repo-alex\ai-real-estate-assistant)
to "fix" its registry vs compose mismatch — that project is frozen by
policy. Any future port conflict with its hardcoded `:8082` should be
resolved by the **other** side (you, picking a different host port).
