# Port Matrix — ai-news-scraper

> **Source of truth:** the canonical port-registry file (see the
> organisation-level docs for the exact path). Local mirror of the
> `externalLocal.ai-news-scraper` entry (v2.4.0, 2026-07-08).

This document is the **local mirror** of the ai-news-scraper entry in the
canonical port-registry. If you change a port here, change the registry
too (and vice-versa). The two are intentionally duplicated — the registry
is canonical for collision-checking across the whole product family;
this file is the on-disk pointer for ai-news-scraper contributors.

---

## Range conventions

| Resource  | Range         | Increment rule | Source         |
| --------- | ------------- | -------------- | -------------- |
| Frontend  | `3800-3899`   | +1 per product | the port-management guide §"Folder-based Port Ranges" |
| Backend   | `8000-8099`   | +1 per product | same           |
| Database  | `5433-5499`   | +1 per product | same (5432 reserved for shared dev Postgres) |
| Redis     | `6300-6499`   | per-product    | same           |
| ChromaDB  | no formal range (high ports, `8500+`) | n/a     | this repo      |

`8082` is **reserved for another product** (see the registry entry).
ai-news-scraper's backend sits in the next free slot at `8007` to avoid
that collision.

---

## ai-news-scraper — local dev allocation

| Service       | Container port | Host port | Notes |
| ------------- | -------------- | --------- | ----- |
| **web**       | `3000` (Next.js default) | **`3807`** | Browser: `http://localhost:3807`. Replaces the previous default `:3000`. |
| **api**       | `8000` (uvicorn default) | **`8007`** | Browser: `http://localhost:8007`. Swagger at `/docs`. Replaces the previous `:8082` (which clashed with the reserved slot). |
| **database**  | `5432` (Postgres default) | **`5440`** | Dev-only; `pgdata` named volume persists across restarts. Replaces shared `5432`. |
| **redis**     | `6379` (Redis default) | **`6380`** | Dev-only isolated Redis; replaces shared `6379`. `redisdata` named volume. |
| **chromadb**  | `8000` (ChromaDB HTTP) | **`8500`** | Replaces previous `:8000` which clashed with another backend. `chromadata` named volume. |

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
| `8082` (api)  | reserved for another product (registry v2.x) + a public frozen repo's `docker-compose.quick.yml:8082:8000` |
| `8000` (chromadb) | another backend (registry v.x)                    |
| `3000` (web)  | Standard Next.js default (out of the 3800-3899 range)  |
| `5432` (db)   | shared dev Postgres                                     |
| `6379` (redis)| shared dev Redis                                        |

After the fix the only reserved/canonical port used by ai-news-scraper is
**5432 inside containers** (Postgres) and **6379 inside containers**
(Redis) — the compose host-side mappings put everything in the canonical
3800+ / 8000+ ranges.

---

## Related products' ports (per `externalLocal`)

| Product                          | Frontend | Backend  | Database | Other        |
| -------------------------------- | -------- | -------- | -------- | ------------ |
| sibling CV repo                  | `3001`   | `8001`   | n/a      | n/a          |
| public demo (quick compose)      | `???`    | `8082` ⚠️ | n/a     | ⚠️ frozen repo — see note |
| ai-news-scraper (this repo)       | **`3807`** | **`8007`** | **`5440`** | redis `6380`, chroma `8500` |

⚠️ The public demo's `docker-compose.quick.yml:8082:8000` is **out of sync**
with its registry allocation of `8004`. Per project policy that repo is
**frozen** (public demo, no further changes). The mismatch between its
compose and the registry is therefore **accepted as-is** and **must not**
be auto-fixed from this repo. New products continue to avoid the `8082`
slot for that reason.

---

## When you change a port

1. Update the code files in `docker-compose.yml`, `apps/api/api/config.py`,
   `apps/api/Dockerfile`, `apps/web/Dockerfile`, `.env.example`,
   `scripts/dev/{run,status}.ps1`, `CLAUDE.md`.
2. Bump the version in the canonical port-registry file
   (semver: +0.0.1 if additive only) and add a `changelog` entry.
3. Mirror the change here in `docs/ports.md` (this file).
4. Run `bash <path-to>/show-ports.ps1` to check no other registered
   product now collides.
5. Tear down and bring the stack back up with `pwsh scripts/dev/{stop,run}.ps1`
   so the new host ports take effect.

**Do NOT** touch the public demo to "fix" its registry vs compose mismatch
— that project is frozen by policy. Any future port conflict with its
hardcoded `:8082` should be resolved by the **other** side (you, picking
a different host port).
