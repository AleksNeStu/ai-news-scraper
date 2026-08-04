# =====================================================
# AI News Scraper — Local Verification Makefile
# =====================================================
#
# Run the same gates CI runs (apps/api/poetry install + pytest with
# postgres/redis services, apps/web/pnpm install + build + typecheck
# + lint, private-leak-check on tracked files) without round-tripping
# to GitHub Actions. Run `make pre-push` before pushing.
#
# Targets
#   make pre-push          Full CI parity (5/5): leak-check + ruff +
#                          pytest + pnpm build + axe-core. The canonical
#                          pre-push gate. ~5-10 min first run (downloads
#                          chromium), ~30-60s after.
#   make pre-push-fast     4/5 parity (no a11y). ~30-60s. For quick
#                          pre-commit feedback when you haven't touched
#                          apps/web/e2e/**.
#   make ci-local          Alias for pre-push-fast.
#   make ci-local-a11y     Alias for pre-push.
#   make install-pre-push-hook   Install .git/hooks/pre-push so every
#                          `git push` runs `make pre-push` automatically.
#                          Bypass with `git push --no-verify`.
#   make check             Fast gates only (no Docker, no DB): ruff,
#                          eslint, prettier, tsc, AST, leak-check.
#   make test-api          Python tests with real DBs (postgres + redis).
#                          Brings up Docker services, runs alembic upgrade
#                          head, runs pytest via host venv.
#                          ~2 min first run (image pulls), ~30s after.
#                          Mapped to apps/api's CI 'API — test' job.
#   make test-web          pnpm install (frozen) + build + typecheck + lint.
#                          ~1 min. Mapped to apps/web's CI 'Web — build' job.
#   make leak-check        private-leak-check.sh on all tracked files +
#                          staged commit messages. Catches forbidden
#                          identifiers that would block CI.
#   make test-a11y         Playwright + axe-core scan. Requires
#                          `pnpm exec playwright install --with-deps chromium`
#                          (one-time ~200MB download).
#
# Variables
#   PY            python interpreter (default: python)
#   PNPM          pnpm binary       (default: pnpm)
#   POETRY        poetry binary     (default: poetry)
#   SKIP_DOCKER=1 skips docker-compose targets if Docker is unavailable
# =====================================================

.PHONY: help check test-api test-web leak-check test-a11y ci-local ci-local-a11y pre-push pre-push-fast install-pre-push-hook clean-deps gen-prod-env render-validate smoke-e2e

PY     ?= python
PNPM   ?= pnpm
POETRY ?= poetry

help:
	@echo "AI News Scraper — local verification targets"
	@echo ""
	@echo "  make pre-push          Full CI parity (5/5 checks: lint, test, leak, build, a11y)"
	@echo "  make pre-push-fast     Fast parity (4/5, no a11y): ~30-60s"
	@echo "  make ci-local          Same as pre-push-fast"
	@echo "  make ci-local-a11y     Same as pre-push (5/5)"
	@echo "  make check             Fast gates only (no Docker, no DB): ruff, eslint, prettier, tsc, AST, leak-check"
	@echo "  make leak-check        private-leak-check.sh on all tracked files"
	@echo "  make test-api          Python tests with postgres+redis (Docker + host venv)"
	@echo "  make test-web          pnpm install (frozen) + build + typecheck + lint"
	@echo "  make test-a11y         Playwright + axe-core scan (requires chromium)"
	@echo "  make install-pre-push-hook   Install .git/hooks/pre-push to gate every push"
	@echo ""

# ----- Fast local gates (no Docker) ----------------------------------------

check: check-py check-web leak-check
	@echo ""
	@echo "✓ Local gates passed (no Docker required)."

check-py: ruff api-ast-parse
	@echo "✓ Python gates passed."

ruff:
	@echo "→ Running ruff (matches CI 'API — lint')..."
	@cd apps/api && ruff check . || (echo "✗ ruff failed" && exit 1)

api-ast-parse:
	@echo "→ AST-parsing all Python files in apps/api (catches syntax errors)..."
	@$(PY) -c "import ast, pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('apps/api').rglob('*.py')]; print('  parsed', sum(1 for _ in pathlib.Path('apps/api').rglob('*.py')), 'files')"

check-web: eslint prettier web-ast-parse
	@echo "✓ Web gates passed."

# NOTE: don't pipe through `tail` here — `tail` exits 0 even if the
# upstream command failed, which would mask prettier/eslint/tsc errors.
eslint:
	@echo "→ Running eslint (matches CI 'Web — build' lint step)..."
	@cd apps/web && $(PNPM) exec eslint --max-warnings 0 . 2>&1 || (echo "✗ eslint failed" && exit 1)

prettier:
	@echo "→ Running prettier --check (matches pre-commit-web hook)..."
	@cd apps/web && $(PNPM) exec prettier --check . || (echo "✗ prettier failed — run 'pnpm exec prettier --write .' to fix" && exit 1)

web-ast-parse:
	@echo "→ Running tsc --noEmit (full type-check; matches CI 'Web — build' typecheck step)..."
	@cd apps/web && $(PNPM) exec tsc --noEmit --pretty false 2>&1 || (echo "✗ tsc failed" && exit 1)

# ----- Private-leak-check (matches CI 'private-leak-check' workflow) --------

# Mirrors what `.github/workflows/private-leak-check.yml` runs on CI:
# scans every tracked file + the staged commit messages for forbidden
# identifiers (canonical pattern list in scripts/private-leak-check.sh).
# Catches the case where a commit adds private-infra references in
# code or commit body that would block CI.
leak-check: leak-check-files leak-check-msg
	@echo "✓ private-leak-check passed."

leak-check-files:
	@echo "→ Scanning tracked files for forbidden identifiers (private-leak-check.sh)..."
	@# Pipeline note: `xargs -0 cat` may print "environment is too large for
	@# exec" to STDERR on Windows for very large repos, but cat still
	@# completes. We swallow that noise via 2>/dev/null; the actual content
	@# is on STDOUT, which `bash scripts/private-leak-check.sh` consumes.
	@git ls-files -z -- \
		':!scripts/private-leak-check.sh' \
		':!poetry.lock' \
		':!pnpm-lock.yaml' \
		':!apps/api/poetry.lock' \
		| xargs -0 cat 2>/dev/null \
		| bash scripts/private-leak-check.sh \
		|| (echo "✗ private-leak-check failed on tracked files" && exit 1)

# Stage-aware: only scans when there are staged changes (i.e. the user
# is about to commit). If working tree is clean, skip.
leak-check-msg:
	@if git diff --cached --quiet 2>/dev/null; then \
		echo "→ No staged changes — skipping commit-message scan."; \
	else \
		echo "→ Scanning staged commit message for forbidden identifiers..."; \
		git diff --cached --format=%B | bash scripts/private-leak-check.sh --message /dev/stdin \
			|| (echo "✗ private-leak-check failed on staged commit message" && exit 1); \
	fi

# ----- API tests with real DBs (Docker) ------------------------------------

# Uses host venv (poetry install + run pytest) inside the repo, with
# postgres + redis brought up via docker-compose. The API Dockerfile
# only installs --only main (no pytest, no dev deps) so we deliberately
# do NOT use `docker compose run --rm api pytest` (would fail with
# "ModuleNotFoundError: pytest"). The host venv path is the CI-parity
# way: Poetry 2.x install + alembic + pytest, matching `.github/workflows/ci.yml`.
test-api:
ifndef SKIP_DOCKER
	@echo "→ Bringing up postgres + redis via docker-compose..."
	@docker compose up -d db redis chromadb migrate 2>&1 | tail -10 || (echo "✗ docker compose up failed" && exit 1)
	@echo "→ Waiting for postgres + redis to be healthy..."
	@for i in $$(seq 1 30); do \
		healthy=$$(docker compose ps --format '{{.Service}}:{{.Health}}' 2>/dev/null | grep -cE ":(healthy)$"); \
		if [ "$$healthy" -ge 2 ]; then echo "  services healthy after $${i}s"; break; fi; \
		sleep 1; \
	done
	@echo "→ Poetry install (host venv)..."
	@cd apps/api && $(POETRY) install --no-interaction 2>&1 | tail -5 || (echo "✗ poetry install failed" && exit 1)
	@echo "→ Running alembic upgrade head..."
	@cd apps/api && $(POETRY) run alembic upgrade head || (echo "✗ alembic upgrade failed" && exit 1)
	@echo "→ Running pytest (matches CI 'API — test')..."
	@cd apps/api && $(POETRY) run pytest -v --tb=short || (echo "✗ pytest failed" && exit 1)
	@echo "→ Tearing down test services..."
	@docker compose down
else
	@echo "SKIP_DOCKER=1 set; skipping pytest (postgres+redis unavailable)."
	@echo "  Use 'docker compose up -d db redis && cd apps/api && poetry run pytest' manually."
endif

# ----- Web build + typecheck + lint (no Docker needed) ---------------------

# Uses --frozen-lockfile (matches CI) so any drift between package.json
# and pnpm-lock.yaml fails locally before the push. Drift here would
# also fail CI, so catching it locally saves a round-trip.
test-web:
	@echo "→ Running pnpm install --frozen-lockfile (matches CI 'Web — build')..."
	@cd apps/web && $(PNPM) install --frozen-lockfile || (echo "✗ pnpm install --frozen-lockfile failed — run 'pnpm install --lockfile-only' to update" && exit 1)
	@echo "→ pnpm build..."
	@cd apps/web && $(PNPM) build 2>&1 | tail -30 || (echo "✗ pnpm build failed" && exit 1)
	@echo "→ pnpm typecheck..."
	@cd apps/web && $(PNPM) typecheck 2>&1 | tail -20 || (echo "✗ pnpm typecheck failed" && exit 1)
	@echo "→ pnpm lint..."
	@cd apps/web && $(PNPM) lint 2>&1 | tail -20 || (echo "✗ pnpm lint failed" && exit 1)
	@echo "✓ Web build + typecheck + lint passed."

# ----- a11y (Playwright + axe-core scan) — optional, opt-in ---------------

# Requires: `pnpm exec playwright install --with-deps chromium` (one-time
# setup). Not in `ci-local` by default because chromium is ~200MB and
# most commits don't touch web/e2e. Run with `make test-a11y` before
# merging a web change, or use `make ci-local-a11y` for the full set.
test-a11y:
	@echo "→ Installing chromium browser (one-time)..."
	@cd apps/web && $(PNPM) exec playwright install --with-deps chromium 2>&1 | tail -5 || (echo "✗ playwright install failed" && exit 1)
	@echo "→ Building web bundle (needed for preview server)..."
	@cd apps/web && $(PNPM) build 2>&1 | tail -5 || (echo "✗ pnpm build failed" && exit 1)
	@echo "→ Starting preview server + running axe-core scan..."
	@cd apps/web && (HOSTNAME=127.0.0.1 PORT=4173 node .next/standalone/apps/web/server.js &) ; echo $$! > .next/standalone/.next-server.pid
	@cd apps/web && BASE_URL=http://127.0.0.1:4173 $(PNPM) exec playwright test e2e/a11y.spec.ts --reporter=list 2>&1 | tail -20 || (echo "✗ a11y scan failed" && exit 1)
	@cd apps/web && [ -f .next/standalone/.next-server.pid ] && kill "$$(cat .next/standalone/.next-server.pid)" 2>/dev/null || true
	@echo "✓ a11y scan passed."

# ----- Full CI parity ------------------------------------------------------

# Mirrors what GitHub Actions runs (excluding a11y — see test-a11y).
# Use this for fast pre-push feedback (~30-60s, no chromium).
ci-local: check test-api test-web
	@echo ""
	@echo "✓✓✓ CI parity check passed. Safe to push."

# Full CI parity including a11y. Use this before merging a web change
# or as the canonical pre-push gate (~5-10min, downloads chromium first run).
# Runs all 5 workflows GitHub Actions would run:
#   - private-leak-check (leak-check)
#   - api-lint (ruff)
#   - api-test (pytest + postgres)
#   - web-build (pnpm + build + typecheck + lint)
#   - a11y (Playwright + axe-core)
ci-local-a11y: ci-local test-a11y
	@echo ""
	@echo "✓✓✓ Full CI parity (with a11y) passed. Safe to push."

# pre-push is the canonical pre-push gate — runs ALL 5 CI workflows.
# Use `make pre-push-fast` for the 4-check version (no a11y).
pre-push: ci-local-a11y

# pre-push-fast = ci-local without a11y. ~30-60s, no chromium download.
pre-push-fast: ci-local

# Install a git pre-push hook that calls `make pre-push`. Once installed,
# every `git push` is gated by the local CI runner. To bypass for a
# specific push: `git push --no-verify`. To uninstall: delete the hook.
install-pre-push-hook:
	@echo "→ Installing pre-push hook in .git/hooks/pre-push..."
	@echo '#!/usr/bin/env bash' > .git/hooks/pre-push
	@echo '# Auto-installed by Makefile target `install-pre-push-hook`.' >> .git/hooks/pre-push
	@echo '# Runs all 5 GitHub Actions workflows locally before pushing.' >> .git/hooks/pre-push
	@echo '# Bypass with `git push --no-verify`.' >> .git/hooks/pre-push
	@echo 'set -e' >> .git/hooks/pre-push
	@echo 'cd "$$(git rev-parse --show-toplevel)" && make pre-push' >> .git/hooks/pre-push
	@chmod +x .git/hooks/pre-push
	@echo "✓ Pre-push hook installed. Every `git push` now runs `make pre-push`."
	@echo "  Test with: git push --dry-run"

# ----- Cleanup -------------------------------------------------------------

clean-deps:
	@echo "→ Removing Docker test services..."
	@docker compose down -v 2>&1 || true
	@echo "→ Clearing pnpm cache..."
	@cd apps/web && $(PNPM) store prune 2>&1 || true

# ----- Ops: generate a production .env ------------------------------------

# gen-prod-env  Walks .env.example and prompts for prod-only values
#               (JWT secrets, CORS, provider keys, SMTP). Writes a
#               chmod 600 .env.production. Never committed (gitignored).
#               Local-prod parity mint; the runtime source-of-truth for
#               Render is the dashboard's sync: false entries (see
#               render.yaml + docs/operations/deploy.md).
gen-prod-env:
	@bash scripts/gen-prod-env.sh

# render-validate  Lint render.yaml against Render's blueprint schema if
#                  the Render CLI is installed. Skips silently otherwise
#                  so the gate still passes for local dev environments.
render-validate:
	@if command -v render >/dev/null 2>&1; then \
	  echo "→ Validating render.yaml against Render Blueprint schema..."; \
	  render blueprint validate --path render.yaml; \
	else \
	  echo "→ Render CLI not installed — skipping render.yaml schema check."; \
	  echo "  Install from https://render.com/docs/cli to enable this gate."; \
	fi

# smoke-e2e  Probe a live production deploy end-to-end. Hits /health, then
#            registers a temp user, scrapes one URL (override with URL/
#            PARAPHRASE), and asserts the article lands in /search top-3.
#            Pass --full to cycle through three URL/paraphrase pairs.
#
#            Requires: BASE_URL set (Render web origin), jq + curl + the
#            BSD/GNU openssl CLI installed, and an LLM provider key
#            configured in the Render dashboard — otherwise the embedding
#            step silently returns None and the search assertion fails.
#
#            For daily CI / production acceptance, the full battery is
#            the Phase-2 --full sweep; for deploy-time verification the
#            default single-URL pass is enough.
smoke-e2e:
	@BASE_URL=$${BASE_URL:?Set BASE_URL=https://ai-news-scraper-web.onrender.com} \
	  bash scripts/smoke-e2e.sh
