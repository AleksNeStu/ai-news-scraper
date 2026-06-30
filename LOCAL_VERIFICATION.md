# Local Verification

Run the same gates that GitHub Actions runs **without** round-tripping
through CI. Built so you can verify a change before pushing.

## TL;DR

```bash
# Fast gates only — ruff + eslint + prettier + AST. ~30s, no Docker.
make check

# Full CI parity — runs check + pytest with postgres+redis + pnpm build.
# ~3 min first run (image pulls), ~1 min after.
make ci-local

# Or just the bash wrapper if you don't have make on PATH.
./scripts/check.sh ci-local
```

## What each gate does (and what it doesn't)

| Gate | What it catches | What it doesn't catch |
|---|---|---|
| `ruff check` | Python linting (unused imports, undefined names, complexity) | Type errors, runtime errors |
| `python -c "ast.parse(...)"` | Syntax errors in every `.py` file | Semantic errors, missing imports |
| `pnpm exec eslint` | Web lint (React hooks rules, a11y, no-console) | Type errors |
| `pnpm exec prettier --check` | Formatting drift in TS/TSX/JSON | Real bugs |
| `pnpm exec tsc --noEmit` | Type errors across the web app | Runtime errors |
| `docker compose run --rm api poetry run pytest` | The full API test suite with real Postgres + Redis | Frontend regressions |
| `pnpm build` | Next.js production build (page rendering, Suspense, typed routes) | Anything not exercised at build time |

The `make ci-local` target maps directly to the three CI jobs:

| CI job | Makefile target |
|---|---|
| `API — lint` | `make ruff` |
| `API — test` (pytest with postgres + redis services) | `make test-api` |
| `Web — build` (pnpm install + build + typecheck + lint) | `make test-web` |

## Before every commit

```bash
make check
```

If that passes, the change is at least syntactically and lint-wise
correct. If `make check` is clean, push and let CI handle the
full test suite.

## Before pushing

```bash
make ci-local
```

This brings up the docker-compose services (`db`, `redis`),
runs pytest, then runs `pnpm build` + `typecheck` + `lint`.
If everything passes, push should be safe.

## Install the local pre-push hook

To make `make ci-local` run automatically before every push:

```bash
# Option A — symlink the Makefile target into the git pre-push hook
ln -sf ../../Makefile .git/hooks/pre-push

# Option B — wrap in a tiny shell hook
cat > .git/hooks/pre-push <<'EOF'
#!/usr/bin/env bash
make ci-local || exit 1
EOF
chmod +x .git/hooks/pre-push
```

Note: this replaces the canonical RepoALX pre-push cascade hook.
Don't enable it on multiple clones — pick one or the other.

## When to skip Docker

If Docker isn't available, set `SKIP_DOCKER=1`:

```bash
SKIP_DOCKER=1 make ci-local
```

You'll get `check` (always) and `test-web` (always) but pytest
will print a notice and skip. Pytest still runs the import-collection
phase, which catches a meaningful chunk of import-time errors.

## Known local vs CI differences

1. **Lockfile**: `poetry.lock` and `pnpm-lock.yaml` are not committed
   to the repo (the dev sandbox can't reach pypi.org / npmjs.org).
   Local installs regenerate them; CI regenerates them too (the
   `--no-update` and `--frozen-lockfile` flags were removed in commits
   `3961e69` and `51466eb`).

2. **Pre-commit hooks vs make check**: the hooks are a subset of
   `make check` (no `eslint --max-warnings 0`, no AST parse, no tsc).
   `make check` is the strict superset — pass it and you've passed
   every pre-commit hook.

3. **Push trigger**: the `ci.yml` workflow now has `workflow_dispatch`
   trigger (added in commit `81e9016`), so even if the push event is
   skipped, you can manually trigger via:
   ```bash
   GH_TOKEN="$GITHUB_TOKEN_AVN" gh workflow run ci.yml --ref dev
   ```

## Related

- `.pre-commit-config.yaml` — the commit-time hooks (subset of `make check`)
- `.github/workflows/ci.yml` — the CI definition these targets mirror
- `docker-compose.yml` — the services `make test-api` brings up
- `Makefile` — the actual targets