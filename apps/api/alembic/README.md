# Alembic — Database Migrations

This directory holds the Alembic configuration for the ai-news-scraper API.
Alembic is the schema-versioning layer that produces the DDL applied to the
project's PostgreSQL database. The Python models under `apps/api/api/models/`
are the source of truth for application-level schema; the Alembic revisions
under `alembic/versions/` translate those models into explicit DDL so that a
fresh database can be brought up reproducibly and destructive changes can be
audited as code. The async wiring (`async_engine_from_config` + `NullPool` +
`run_sync(do_run_migrations)`) is configured in `env.py` so that Alembic can
talk to the same async SQLAlchemy stack the FastAPI app uses at runtime.

## Common commands

All commands assume `cwd = apps/api`.

```bash
# Show the currently-applied revision on the target DB.
poetry run alembic current

# Show the full revision graph (head, branches, depends_on).
poetry run alembic history

# Apply all pending migrations to the database pointed at by $DATABASE_URL.
poetry run alembic upgrade head

# Roll every applied migration back to nothing (destructive — wipes schema).
poetry run alembic downgrade base

# Emit the full DDL script to stdout WITHOUT touching any database.
# Useful for code review, dry-runs, and CI smoke-checks.
poetry run alembic upgrade head --sql
```

## Loading seed data (idempotent dev seed)

```bash
# Bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f apps/api/scripts/seed.sql

# Or use the wrappers (same contract, both read $DATABASE_URL):
apps/api/scripts/seed.sh
apps/api/scripts/seed.ps1
```

See `apps/api/scripts/seed.sql` for the contents (one user, two feeds,
four articles, four feed_items). Every insert is `ON CONFLICT DO NOTHING`,
so re-running the seed against a populated database is safe.

## Live-DB gate

`alembic upgrade head` and `alembic downgrade base` both require a reachable
PostgreSQL instance. **They are NOT verified by this worktree's local
verification** — Docker is the canonical way to bring up Postgres locally
(`docker compose up -d postgres`), and CI runs these commands against the
containerised database. Use `alembic upgrade head --sql` for offline
verification (DDL emitted to stdout; no DB needed).

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | for online commands (upgrade/downgrade/seed) | `postgresql+asyncpg://postgres:postgres@localhost:5432/ai_news` (from `api.config`) | Connection string. Overrides the empty `sqlalchemy.url` in `alembic.ini`. Never commit a real value — `.env` is gitignored. |
| `ALEMBIC_CONFIG` | no | `alembic.ini` in `cwd` | Alternate path to the Alembic config file (handy in CI/CD or for staging). |

## Files in this directory

| File | Purpose |
|---|---|
| `env.py` | Async-aware migration runner. Imports all 4 models so autogenerate sees the full schema. Reads `DATABASE_URL` from env. |
| `script.py.mako` | Template used by `alembic revision` to scaffold new revision files. |
| `versions/` | One file per migration revision. The initial revision is `1890892bda24_initial_schema.py`. |
| `README.md` | This file. |

## Adding a new migration

1. Edit the model(s) in `apps/api/api/models/`.
2. Generate a candidate revision:
   ```bash
   poetry run alembic revision --autogenerate -m "describe what changed"
   ```
3. **Review the generated file by hand.** Autogenerate is a starting point,
   not a guarantee — column renames, FK `ondelete` changes, and check
   constraints are common sources of false negatives.
4. Add the migration to the next commit alongside the model change.
5. Apply to dev DB: `poetry run alembic upgrade head`.
6. Commit with a Conventional Commits prefix (`feat:`, `fix:`, `refactor:`).
