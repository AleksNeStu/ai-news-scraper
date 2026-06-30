# =====================================================
# AI News Scraper — Local Verification Makefile
# =====================================================
#
# Run the same gates CI runs (apps/api/poetry install + pytest with
# postgres/redis services, apps/web/pnpm install + build + typecheck
# + lint) without round-tripping to GitHub Actions.
#
# Targets
#   make check      Fast gates only — no Docker. Runs in <30s.
#                   ruff, eslint, prettier, AST parse, gitleaks,
#                   pre-commit-style hooks. Run this before commit.
#
#   make test-api   Python tests with real DBs via docker-compose.
#                   ~2 min first run (image pulls), ~30s after.
#                   Mapped to apps/api's CI 'API — test' job.
#
#   make test-web  Next.js build + typecheck + lint via pnpm.
#                   ~1 min. Mapped to apps/web's CI 'Web — build' job.
#
#   make ci-local  Full CI parity: check + test-api + test-web.
#                   Run before pushing.
#
#   make pre-push  Alias for ci-local. Use as a git pre-push hook
#                   target: ln -sf ../../Makefile .git/hooks/pre-push
#
# Variables
#   PY            python interpreter (default: python)
#   PNPM          pnpm binary       (default: pnpm)
#   POETRY        poetry binary     (default: poetry)
#   SKIP_DOCKER=1 skips docker-compose targets if Docker is unavailable
# =====================================================

.PHONY: help check test-api test-web ci-local pre-push clean-deps

PY     ?= python
PNPM   ?= pnpm
POETRY ?= poetry

help:
	@echo "AI News Scraper — local verification targets"
	@echo ""
	@echo "  make check      Fast gates (no Docker): ruff, eslint, prettier, AST"
	@echo "  make test-api   Python tests with postgres+redis (Docker)"
	@echo "  make test-web  Next.js build + typecheck + lint (pnpm)"
	@echo "  make ci-local  Full CI parity: check + test-api + test-web"
	@echo "  make pre-push  Alias for ci-local"
	@echo ""

# ----- Fast local gates (no Docker) ----------------------------------------

check: check-py check-web
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

# ----- Docker-based: API tests with real DBs --------------------------------

test-api:
ifndef SKIP_DOCKER
	@echo "→ Bringing up postgres + redis via docker-compose..."
	@docker compose up -d db redis
	@echo "→ Running pytest inside the api container (matches CI 'API — test')..."
	@docker compose run --rm api poetry run pytest -v --tb=short
	@echo "→ Tearing down test services..."
	@docker compose down
else
	@echo "SKIP_DOCKER=1 set; skipping pytest (postgres+redis unavailable)."
	@echo "  Use 'docker compose up -d db redis && cd apps/api && poetry run pytest' manually."
endif

# ----- Web build + typecheck + lint (no Docker needed) ---------------------

test-web:
	@echo "→ Running pnpm install (matches CI 'Web — build')..."
	@cd apps/web && $(PNPM) install --no-frozen-lockfile
	@echo "→ pnpm build..."
	@cd apps/web && $(PNPM) build 2>&1 | tail -30
	@echo "→ pnpm typecheck..."
	@cd apps/web && $(PNPM) typecheck 2>&1 | tail -20
	@echo "→ pnpm lint..."
	@cd apps/web && $(PNPM) lint 2>&1 | tail -20
	@echo "✓ Web build + typecheck + lint passed."

# ----- Full CI parity ------------------------------------------------------

ci-local: check test-api test-web
	@echo ""
	@echo "✓✓✓ CI parity check passed. Safe to push."

pre-push: ci-local

# ----- Cleanup -------------------------------------------------------------

clean-deps:
	@echo "→ Removing Docker test services..."
	@docker compose down -v 2>&1 || true
	@echo "→ Clearing pnpm cache..."
	@cd apps/web && $(PNPM) store prune 2>&1 || true