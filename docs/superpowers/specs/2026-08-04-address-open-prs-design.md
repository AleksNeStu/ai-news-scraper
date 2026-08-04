# Address All Open PRs — Design

**Date:** 2026-08-04
**Goal origin:** `/goal address all open prs` (set in `ai-news-scraper` checkout, dev branch)
**Status:** Draft v1, awaiting user review

---

## Context

`ai-news-scraper` has **11 open Dependabot PRs** (all dependency bumps, none reviewed since 2026-07-13). Across the RepoALX collection, `gh pr list` surfaces **42 open PRs total**:

| Repo | Open PRs | Visibility | Token access |
|---|---|---|---|
| `ai-news-scraper` | 11 (all Dependabot) | public | yes |
| `ai-real-estate-assistant` | 1 (dependabot-auto-merge CI fix) | public | yes |
| `natively-cluely` | 30 (mix: features, fixes, deps) | private | yes |
| `cv` | unknown (token 404s) | private mirror-only | **no** |
| `EBiCS_Firmware` | unknown (token 404s) | private mirror-only | **no** |

GH Actions are paused repo-wide per project policy; CI is not gating merges automatically.

The project's "no PRs to main" rule (memory note 2026-07-09) covers human-authored PRs but does not address bot PRs (Dependabot) which have accumulated since. PRs in `natively-cluely` (private) appear to predate the dev-only workflow and have been waiting for review.

---

## Goal

Per user's clarifications:

1. **"Address" means** — review each PR, take action (merge / close / request changes), document the decision.
2. **Scope** — all accessible repos (3 of 5; skip `cv` + `EBiCS_Firmware`).
3. **Decision criteria** — merge if unconflicted + CI green-or-paused + semver-safe; close if conflicts / CI fail / policy conflict; request changes if ambiguous.

---

## Architecture

Single in-session agent drives a per-repo loop. No subagents (42 PRs × ~5min each is bounded). `gh` CLI is already authenticated as `AleksNeStu` (active account) — no token switch needed.

```
for repo in [ai-news-scraper, ai-real-estate-assistant, natively-cluely]:
    inventory = gh pr list -R <repo> --state open --json ...
    for pr in inventory:
        if is_Dependabot(pr) and repo == ai-news-scraper:
            spot_check 2-3; if uniform, batch_merge rest with --auto
        else:
            per_pr_review(pr)
        decide(pr) → MERGE | CLOSE | REQUEST_CHANGES | LEAVE_OPEN
        act(pr, decision, rationale)
        audit(pr, decision, rationale, commit_or_close_sha)
```

---

## Components

- **Inventory collector** — `gh pr list -R <repo> --state open --json number,title,author,createdAt,isDraft,mergeable,labels,url`
- **Decision matrix** — pure function over PR fields:
  - `mergeable=false` → CLOSE ("merge conflict — auto-close, recreate from updated base")
  - `labels includes "dependencies"` + `ai-news-scraper` + semver-safe → MERGE (Dependabot batch)
  - `labels includes "dependencies"` + major bump → CLOSE ("major bump requires manual review")
  - CI check status = `failure` → LEAVE_OPEN + comment ("CI failing, deferring")
  - CI status ∈ {success, neutral, skipped} → eligible for MERGE
  - Draft PR → LEAVE_OPEN + comment ("not ready for review")
  - Human-authored PR requiring judgment → REQUEST_CHANGES with specific feedback
- **Action executor** — `gh pr merge --squash --delete-branch --body "<rationale>"` or `gh pr close --comment "<reason>"` or `gh pr review --request-changes --body "<feedback>"`
- **Audit log** — `docs/operations/pr-triage-2026-08-04.md`, append-only, one row per PR.

---

## Data flow

```
gh pr list (per repo) → JSON inventory (in-memory)
  ↓
for each PR:
    gh pr view N (already in inventory for most fields)
    gh pr checks N → CI status
    if ambiguous: gh pr diff N
  ↓
decision matrix → MERGE | CLOSE | REQUEST_CHANGES | LEAVE_OPEN
  ↓
action:
    MERGE          → gh pr merge N --squash --delete-branch --body "<rationale>"
    CLOSE          → gh pr close N --comment "<reason>"
    REQUEST_CHANGES→ gh pr review N --request-changes --body "<feedback>"
    LEAVE_OPEN     → gh pr comment N --body "<why-deferred>"
  ↓
audit row → docs/operations/pr-triage-2026-08-04.md
  ↓
final check: gh pr list -R <repo> --state open → 0 PRs (or all = LEAVE_OPEN with rationale)
```

---

## Error handling

- **`gh` rate limit (HTTP 429)** — wait 60s, retry once, fail loudly on second 429. Don't burn the rate budget.
- **Merge conflict surfaces during `gh pr merge`** — mark CLOSE with "resolved to conflict during merge attempt" reason. Don't auto-rebase (project policy forbids force-push).
- **Token scope missing** — surface to user; don't silently fall back.
- **Network timeout on individual PR** — log + skip + LEAVE_OPEN with comment "could not retrieve, please retry".
- **Self-merge (PR authored by current `gh` user)** — skip auto-merge; flag for user confirmation (per Rule 154 — never silently self-merge with the user's own credentials).

---

## Testing

- **No unit tests** — operational task, no code change.
- **Validation gate**: at the end, `gh pr list -R <repo> --state open --json number --jq 'length'` returns 0 for each repo, OR returns only PRs marked LEAVE_OPEN with documented rationale in the audit log.
- **Per-action confirmation**: each merge/close emits a clear stdout line so we can verify mid-run.
- **Pre-flight**: confirm `gh auth status` shows the right account (`AleksNeStu`) before any destructive action.

---

## Audit log format

`docs/operations/pr-triage-2026-08-04.md`:

| # | Repo | PR | Title | Decision | Rationale | Commit/Close SHA | Timestamp |
|---|---|---|---|---|---|---|---|

Append-only. No reformatting. The file is the source of truth for what was done.

---

## Out of scope (explicit)

- `cv` + `EBiCS_Firmware` (inaccessible token; user opted to skip).
- Local CI re-run (GH Actions paused per repo policy).
- Per-PR local test execution (would require checkouts of all 3 repos).
- Force-push / rebase to fix conflicts (project policy forbids; Rule 250).
- Comments on external-contributor PRs (none expected; all 42 are Dependabot or `AleksNeStu` org).

---

## Done criteria

The `/goal` is met when **all of the following hold**:

1. Every accessible PR has a decision in the audit log (MERGE / CLOSE / REQUEST_CHANGES / LEAVE_OPEN).
2. Every MERGE produced a squash commit on the target branch.
3. Every CLOSE has a comment with rationale.
4. Every REQUEST_CHANGES has a review with specific feedback.
5. Every LEAVE_OPEN has a comment explaining what's needed next.
6. `gh pr list -R <repo> --state open` for each of the 3 repos shows either 0 PRs OR only the documented LEAVE_OPENs.