# Contributing to AI News Search

Thanks for your interest in contributing! This project is open source, MIT-licensed, and built in the open. This guide covers the basics; for the **hard rules** (public/private boundary, git hygiene, branch discipline) read [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md) first.

## Quick start

```bash
git clone https://github.com/AleksNeStu/ai-news-scraper.git
cd ai-news-scraper
cp .env.example .env  # then edit with your OpenAI key + secrets
docker compose up -d  # postgres + redis + chromadb + api + web
open http://localhost:3000
```

For app-only dev: see the **Run / test / lint** section in [`README.md`](README.md).

## Code style

- **Python** (apps/api): Ruff (`poetry run ruff check .`), 100-char lines, type hints.
- **TypeScript** (apps/web): ESLint Next.js config, Prettier, `pnpm lint` and `pnpm typecheck`.
- **No GPL/AGPL packages** anywhere — see [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md).

## Branch discipline

- `dev` is the **active development branch**. Branch from `dev`.
- `main` is **canonical**. Open PR `dev → main` to land changes.
- No direct push to `main`. No force-push to any remote without explicit owner approval.
- Branch names: `feat/short-desc`, `fix/short-desc`, `chore/short-desc`, `docs/short-desc`.

## Commit convention

Conventional Commits, English only:

```
type(scope): short description (max 72 chars)

[optional body — explain WHY, not WHAT]

[optional footer — Refs #123, BREAKING CHANGE, etc.]
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `style`, `perf`.

Examples:

```
feat(api): add /scrape/batch endpoint for up to 50 URLs
fix(web): resolve "View full text" bug on article detail page
docs(rules): clarify PRIVATE scope gitignore list
```

Do **NOT** include AI co-author lines (`Co-Authored-By: Claude ...`). Solo project, no co-authors.

## PR process

1. Branch from `dev`.
2. Implement + test locally (`poetry run pytest`, `pnpm test`, `pnpm build`).
3. Run linters (`ruff check`, `pnpm lint`).
4. Push to `main` remote `dev` branch — pre-push hook cascades to mirrors.
5. Open PR `dev → main` against `AleksNeStu/ai-news-scraper`.
6. **Fill the PR template** — the public/private boundary checkbox is the most important field.
7. CI must pass (api lint + test, web build/typecheck/lint).
8. Squash-merge when approved.

## Hard rules (the short list)

Full version: [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md). The non-negotiables:

- ✅ **DO** commit source code, public docs, CI workflows.
- ❌ **DO NOT** commit secrets, API keys, `.env` files.
- ❌ **DO NOT** commit internal state — `.agent/`, `CLAUDE.md`, `DESIGN.md`, `docs/research/`, `.taskmaster/`, `.claude/`, `.roomodes`, `.windsurfrules`, `.cursor/`, `.vscode/mcp.json`.
- ❌ **DO NOT** commit AI agent chat history or scratch notes.
- ❌ **DO NOT** force-push to `main`.
- ❌ **DO NOT** introduce GPL/AGPL dependencies.

## Code of conduct

By participating you agree to the [Contributor Covenant v2.1](.github/CODE_OF_CONDUCT.md).

## Reporting security issues

**Do not file public issues for security bugs.** Email `a.v.nesterovich@gmail.com` with subject prefix `[SECURITY]`. See [`SECURITY.md`](SECURITY.md) for the full policy.

## Pre-commit hooks

This repo uses [pre-commit](https://pre-commit.com/) to run lint, format, and secret-scan checks on every commit. Hooks auto-run after `git commit`; you can also run them manually.

### One-time install

```bash
pip install pre-commit
pre-commit install
```

This installs the hook scripts into `.git/hooks/`. Re-run `pre-commit install` after cloning on a new machine.

### Run on demand

```bash
# Run on staged files
pre-commit run

# Run on every file in the repo (slower — first-time CI check)
pre-commit run --all-files

# Update hook SHAs to newer pinned versions
pre-commit autoupdate
```

### What's wired up

| Hook | Purpose |
|---|---|
| `pre-commit/pre-commit-hooks` | File hygiene (trailing whitespace, EOF newlines, large files, merge-conflict markers, LF line endings) |
| `astral-sh/ruff-pre-commit` | Python lint + format (`ruff check --fix`, `ruff format`) |
| `gitleaks/gitleaks` | Secret scan — blocks API keys, tokens, private keys before they land |
| `eslint` (local `pnpm exec`) | TypeScript / React lint for `apps/web/**` (uses the same version as `pnpm lint`) |
| `prettier` (local `pnpm exec`) | Format `apps/web/**` (uses the same version as `pnpm format`) |
| `ruff check` (via Poetry) | Belt-and-braces lint for `apps/api/**` |

### Excluded paths

Hooks are skipped on agent state and internal docs — these are never meant to be in VCS anyway, but the exclude protects against accidental staging:

- `.agent/`, `.taskmaster/`, `.claude/`
- `docs/research/`
- `tasks/`
- `legacy/streamlit/`

### Bypassing (rare)

If you must skip a hook for a single commit (e.g. WIP commit), use:

```bash
git commit --no-verify -m "wip: ..."
```

**Don't make this a habit.** Pre-commit failures usually mean the code needs fixing.

## License

By contributing you agree your contributions are licensed under the [MIT License](LICENSE).
