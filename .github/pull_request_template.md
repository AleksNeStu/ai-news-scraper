<!--
Thanks for contributing to AI News Search!
Please fill out the sections below. The PUBLIC/PRIVATE boundary check is the most
important — it protects contributors and the project owner from accidentally
publishing personal notes / AI tooling config.
-->

## Description

<!-- One paragraph: what does this PR do and why? -->

## Type of change

<!-- Delete options that don't apply -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update
- [ ] Refactor (no behavior change)

## PUBLIC/PRIVATE boundary check (REQUIRED)

> **The single most important checkbox on this template.** Read [`docs/PROJECT_RULES.md`](../docs/PROJECT_RULES.md) before submitting.

- [ ] I have **NOT** committed any file from the **PRIVATE** scope (`.agent/`, `CLAUDE.md`, `DESIGN.md`, `docs/research/`, `.taskmaster/`, `.claude/`, `.roomodes`, `.windsurfrules`, `.cursor/`, `.vscode/mcp.json`, `.env`, `.env.local`, etc.)
- [ ] I have **NOT** committed any secrets, API keys, tokens, or `.env` files.
- [ ] I have **NOT** introduced any GPL/AGPL dependencies.
- [ ] My commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (English only, no AI co-author line).
- [ ] I have branched from `dev` and am targeting `dev → main`.

## Checklist

- [ ] My code follows the project's style (Ruff for Python, ESLint/Prettier for TypeScript).
- [ ] I have performed a self-review of my own code.
- [ ] I have commented my code, particularly in hard-to-understand areas.
- [ ] I have updated the documentation (`docs/`, `README.md`) as needed.
- [ ] My changes generate no new warnings.
- [ ] I have added tests that prove my fix is effective or that my feature works.
- [ ] New and existing unit tests pass locally with my changes (`poetry run pytest`, `pnpm test`).
- [ ] Any dependent changes have been merged and published in downstream modules.

## Testing

<!-- How did you test this? What did you verify manually? -->

## Screenshots (if applicable)

<!-- Add screenshots / GIFs for UI changes. -->