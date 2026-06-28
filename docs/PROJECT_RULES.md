# Project Rules — AI News Search

> **Hard rules for this project.** Public. Bound by the MIT license. Anyone working on this repo (human or AI agent) must follow.

This document is the **canonical source of truth** for what is and isn't allowed in this repository. `CONTRIBUTING.md` is the human-friendly summary; `AGENTS.md` is the AI-agent-friendly version. When in conflict, this document wins.

---

## 1. Mission

**Public OSS-as-resume signal** for backend / data-engineering / AI-engineering hiring managers and consulting clients. The GitHub profile is the product; the code is the proof.

Secondary (acceptable but not central): GitHub Sponsors, Polar.sh tip jar.

**Watch for the social fork opportunity** — keep the project forkable into a separate scoped project (new features, new domain, different audience). No proprietary dependencies, no hardcoded personal paths, no organization-specific config.

---

## 2. PUBLIC scope (always tracked, always safe to commit)

| Path | Purpose |
|---|---|
| `apps/api/**` | FastAPI backend |
| `apps/web/**` | Next.js frontend |
| `packages/shared/**` | TS types shared between api + web |
| `docs/PRD.md`, `docs/CI-CD.md`, `docs/README.md`, `docs/TASK_MANAGEMENT.md`, `docs/TASKMASTER_GUIDE.md`, `docs/COMPETITIVE_ANALYSIS.md`, `docs/COMPREHENSIVE_TODO.md` | Public docs |
| `docs/PROJECT_RULES.md` (this file) | Hard rules |
| `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `SECURITY.md`, `CHANGELOG.md`, `LICENSE` | Public top-level docs |
| `.github/CODE_OF_CONDUCT.md`, `.github/pull_request_template.md`, `.github/FUNDING.yml`, `.github/CODEOWNERS`, `.github/workflows/`, `.github/dependabot.yml` | GitHub-side configuration |
| `docker-compose.yml`, `.env.example`, `pyproject.toml` (root workspace), `pnpm-workspace.yaml` | Repo config |
| `legacy/streamlit/**` | Frozen Streamlit UI (historical reference) |

---

## 3. PRIVATE scope (always gitignored — NEVER commit, NEVER force-add)

These are the **project owner's personal notes and tooling state**. An AI agent must NEVER propose adding them to the tracked set. A contributor must NEVER open a PR that includes them.

| Path | Why private |
|---|---|
| `.agent/**` (PRD, ADRs) | Personal product-planning notes |
| `CLAUDE.md` (repo root) | Project owner's personal Claude Code instructions |
| `DESIGN.md` (repo root) | Personal design notes — the public counterpart is the design's CSS variables in `apps/web/src/app/globals.css` |
| `docs/research/**` | Personal strategy / deep-research notes |
| `.taskmaster/**` | TaskMaster workflow state (local MCP only) |
| `.claude/**` | Claude Code local state |
| `.roomodes` | Roo Code IDE config |
| `.windsurfrules`, `.windsurf/**` | Windsurf IDE config |
| `.cursor/**` | Cursor IDE config |
| `.vscode/mcp.json` | VS Code MCP server config (may contain internal paths / tokens) |
| `.mcp.json`, `**/mcp.json` | MCP server configs generally |
| `.aider*`, `.continue/**` | Aider / Continue.dev chat history |
| `.env`, `.env.local`, `.env.*` (except `.env.example`) | Secrets |

**Rule of thumb**: if a file exists because of a **personal tool the owner runs** (Claude Code, Roo, Windsurf, TaskMaster, Aider, Continue) OR contains **personal planning notes** (PRD drafts, ADRs, design scratch, research) → PRIVATE.

---

## 4. Git hygiene

- **No secrets** — ever. Even in tests. Even temporarily. Use `.env` (gitignored).
- **No `.env` files tracked** — only `.env.example`.
- **No tracked files from PRIVATE scope** — verify with `git ls-files | grep -E "^(\.agent/|DESIGN\.md|^CLAUDE\.md|docs/research/|\.taskmaster/|...)"`.
- **No GPL/AGPL dependencies** — license check before adding any package.
- **No AI co-author lines** in commits (e.g. `Co-Authored-By: Claude ...`). Solo project.
- **Commit messages: English only.** Code: English comments only. (No Chinese / Cyrillic in code, per global CLAUDE.md.)

---

## 5. Branch discipline

- **`dev`** — active development branch. All work happens here. Branch from `dev`.
- **`main`** — canonical, frozen-ish. Only updated via PR `dev → main`.
- **No direct push to `main`** by anyone (including the owner).
- **No force-push to `main`** under any circumstance.
- **Force-push to mirrors** (`mirror1` / `mirror2`) requires explicit owner approval and must use `--force-with-lease`.

Branch naming: `feat/<scope>-<desc>`, `fix/<scope>-<desc>`, `chore/<scope>-<desc>`, `docs/<scope>-<desc>`, `refactor/<scope>-<desc>`.

---

## 6. Commit convention

Conventional Commits, English only:

```
type(scope): short description

[optional body]
[optional footer]
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `style`, `perf`.

**One logical change per commit.** Squash locally before pushing if needed.

---

## 7. Code of conduct & community

- Contributor Covenant v2.1 — see [`.github/CODE_OF_CONDUCT.md`](../.github/CODE_OF_CONDUCT.md).
- Security issues: private email to `a.v.nesterovich@gmail.com` with subject prefix `[SECURITY]`. See [`SECURITY.md`](../SECURITY.md).
- License: MIT — see [`LICENSE`](../LICENSE).

---

## 8. Future-fork checklist

This project is intentionally structured to allow a clean **fork into a separate scoped project** (e.g., vertical-specific spin-off, paid SaaS wrapper, different audience). Before forking:

- [ ] Remove project-specific topics from GitHub repo settings.
- [ ] Update `pyproject.toml` `name` field and `package.json` `name` field.
- [ ] Replace workspace name `ai-news-scraper` throughout.
- [ ] Re-license if needed (MIT is permissive — derivative projects can re-license).
- [ ] Replace owner handle `@AleksNeStu` in `CODEOWNERS`, `FUNDING.yml`, `pull_request_template.md`.
- [ ] Audit that no proprietary dependencies snuck in.
- [ ] Audit that no hardcoded personal paths or tokens remain.

---

## 9. Anti-patterns (project-specific)

Things an agent will do wrong if it doesn't read this file:

- ❌ **DO NOT** commit `DESIGN.md` — it's personal design notes. The public design lives in `apps/web/src/app/globals.css` CSS variables.
- ❌ **DO NOT** commit `CLAUDE.md` (root) — it's the owner's personal agent instructions.
- ❌ **DO NOT** commit `.agent/PRD.md` or `.agent/adr/*` — private planning.
- ❌ **DO NOT** commit `.taskmaster/` — local MCP workflow state.
- ❌ **DO NOT** commit `.roomodes`, `.windsurfrules`, `.cursor/`, `.vscode/mcp.json` — IDE/AI tooling config.
- ❌ **DO NOT** introduce GPL/AGPL packages.
- ❌ **DO NOT** add `Co-Authored-By: Claude ...` (or any AI) to commit messages.
- ❌ **DO NOT** push directly to `main`.
- ❌ **DO NOT** force-push to `main` — history is append-only.
- ❌ **DO NOT** modify `legacy/streamlit/` — frozen for historical reference.
- ❌ **DO NOT** mirror the reference repo (`ai-real-estate-assistant`) verbatim — it uses zinc palette + Fraunces only; this project uses news/data-feel (deep navy + cyan + amber warn).
- ❌ **DO NOT** skip the public/private boundary check in the PR template.

---

## 10. Verification commands

```bash
# Verify no private files are tracked
git ls-files | grep -E "^(\.agent/|DESIGN\.md|^CLAUDE\.md|docs/research/|\.taskmaster/|\.claude/|\.roomodes|\.windsurfrules|\.cursor/|\.vscode/mcp\.json)"
# (no output = OK)

# Verify private paths are gitignored
git check-ignore -v .agent CLAUDE.md DESIGN.md docs/research .taskmaster

# Verify public docs are tracked
git ls-files | grep -E "^(CONTRIBUTING\.md|AGENTS\.md|SECURITY\.md|CHANGELOG\.md|LICENSE)$"
```

If any of these fail, **do not push**. Fix the leak first.

---

## 11. Changelog

- 2026-06-28 — Initial hard rules document. Public/private boundary codified. Mirrors structure of `ai-real-estate-assistant` (CONTRIBUTING, AGENTS, SECURITY, CODEOWNERS, FUNDING).