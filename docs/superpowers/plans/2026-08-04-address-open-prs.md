# Address All Open PRs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Review + take action (merge / close / request changes) on every open PR across 3 accessible RepoALX repos. Skip `cv` + `EBiCS_Firmware` (token-inaccessible). Produce an audit log with one row per PR.

**Architecture:** Single in-session agent drives a per-repo loop using `gh` CLI. No subagents (the 3 repos each get their own task; per-PR decisions are short). Hybrid execution: spot-check + batch the 11 Dependabot PRs in `ai-news-scraper`; individual review for the 30 in `natively-cluely`; individual for the 1 in `ai-real-estate-assistant`. Audit log appended after every action.

**Tech Stack:** `gh` CLI (v2.x, already authenticated as `AleksNeStu` on this machine), `git`, bash. No code changes — pure operational task.

**Reference spec:** `docs/superpowers/specs/2026-08-04-address-open-prs-design.md`

**Execution location:** Run from `E:/repo/repo-alex/ai-news-scraper` checkout (dev branch, commit `d85141f` or later). No worktree needed — `gh pr -R owner/repo` does not require local checkouts for the other repos.

---

## Pre-flight (Phase 0)

### Task 0: Verify `gh` auth + token scopes

**Files:**
- Read: `~/.config/gh/hosts.yml` (or run `gh auth status`)
- No writes.

- [ ] **Step 1: Confirm active account**

```bash
gh auth status 2>&1 | head -10
```

Expected output includes:
```
  ✓ Logged in to github.com account AleksNeStu (keyring)
  - Active account: true
```

If `dev-scaler` or `nest-ai-dev` is active instead, switch:
```bash
gh auth switch --user AleksNeStu
```

- [ ] **Step 2: Confirm token scope includes `repo`**

```bash
gh auth status --show-token 2>&1 | grep -E "Token scopes"
```

Expected: `repo` is in the scope list (other scopes like `admin:org` are fine too). If `repo` is missing, the user must re-authorize — STOP and surface to user.

- [ ] **Step 3: Smoke-test repo access**

```bash
gh pr list -R AleksNeStu/ai-news-scraper --state open --json number --jq 'length'
```

Expected: integer ≥ 11. If 0 or error, STOP and surface token issue.

---

### Task 1: Initialize audit log

**Files:**
- Create: `docs/operations/pr-triage-2026-08-04.md`

- [ ] **Step 1: Create empty audit log with header**

```bash
cat > docs/operations/pr-triage-2026-08-04.md <<'EOF'
# PR Triage 2026-08-04

Triage session for the `/goal address all open prs` session. Scope: 3 accessible RepoALX repos (ai-news-scraper, ai-real-estate-assistant, natively-cluely). Skipped: cv, EBiCS_Firmware (token-inaccessible).

| # | Repo | PR | Title | Decision | Rationale | Commit/Close SHA | Timestamp |
|---|---|---|---|---|---|---|---|
EOF
```

- [ ] **Step 2: Verify the file exists and is empty (header only)**

```bash
wc -l docs/operations/pr-triage-2026-08-04.md
```

Expected: `4 docs/operations/pr-triage-2026-08-04.md` (1 header + 3 table rows).

- [ ] **Step 3: Stage but do NOT commit (commit at end of session per Rule 159 / atomic close-out)**

```bash
git add docs/operations/pr-triage-2026-08-04.md
```

---

## Phase 1: ai-news-scraper (11 Dependabot PRs)

### Task 2: Inventory ai-news-scraper open PRs

- [ ] **Step 1: Capture the full inventory**

```bash
gh pr list -R AleksNeStu/ai-news-scraper --state open \
  --json number,title,author,createdAt,isDraft,mergeable,labels,additions,deletions,url \
  --jq '.[] | "#\(.number) | \(.title) | mergeable=\(.mergeable) | draft=\(.isDraft) | +\(.additions)/-\(.deletions) | \(.url)"' \
  > /tmp/ais_pr_inventory.txt
wc -l /tmp/ais_pr_inventory.txt
```

Expected: `11 /tmp/ais_pr_inventory.txt` (matches the known count).

- [ ] **Step 2: Verify each PR is Dependabot + has `dependencies` label**

```bash
gh pr list -R AleksNeStu/ai-news-scraper --state open \
  --json number,labels \
  --jq '.[] | select(.labels | map(.name) | contains(["dependencies"]) | not) | .number'
```

Expected: empty output (all 11 PRs carry the `dependencies` label). If non-empty, those PRs need individual review (fall through to Phase 3-style flow).

---

### Task 3: Spot-check 2-3 Dependabot PRs for uniformity

Pick the 2 smallest + the largest diff to verify the batch-merge assumption.

- [ ] **Step 1: Pick spot-check targets**

```bash
# Smallest 2
gh pr list -R AleksNeStu/ai-news-scraper --state open \
  --json number,additions,deletions \
  --jq 'sort_by(.additions + .deletions) | .[0:2] | .[].number'

# Largest 1
gh pr list -R AleksNeStu/ai-news-scraper --state open \
  --json number,additions,deletions \
  --jq 'sort_by(.additions + .deletions) | .[-1] | .number'
```

- [ ] **Step 2: View the 3 spot-check PRs**

```bash
for n in <smallest1> <smallest2> <largest>; do
  echo "=== PR #$n ==="
  gh pr view -R AleksNeStu/ai-news-scraper $n --json number,title,files,additions,deletions,mergeable
  gh pr checks -R AleksNeStu/ai-news-scraper $n --json name,state
done
```

Expected: each is a single-file dependency bump in `apps/api/pyproject.toml` or `apps/web/package.json` or `.github/workflows/*.yml`. `mergeable=true` for all 3. CI status: `neutral` or `skipped` (GH Actions paused per repo policy).

If any spot-check shows unexpected content (e.g., touching application code, not just deps), STOP the batch and fall through to per-PR review for ALL 11.

---

### Task 4: Batch-merge Dependabot PRs

Only proceed if Task 3 confirmed uniformity.

- [ ] **Step 1: List the PR numbers to merge**

```bash
gh pr list -R AleksNeStu/ai-news-scraper --state open --json number --jq '.[].number'
```

Capture the 11 numbers (e.g., `32 34 35 36 37 39 40 41 44 46 47`).

- [ ] **Step 2: For each PR, merge with squash + delete branch + audit**

```bash
PR_NUMBERS="32 34 35 36 37 39 40 41 44 46 47"
for n in $PR_NUMBERS; do
  result=$(gh pr merge -R AleksNeStu/ai-news-scraper $n --squash --delete-branch --body "Dependabot batch merge: \`$n\` bumps a single dep file (pyproject.toml / package.json / .github/workflows/*.yml). CI paused per repo policy. squash merge keeps dev history linear." 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    sha=$(gh pr view -R AleksNeStu/ai-news-scraper $n --json mergeCommit --jq '.mergeCommit.oid' 2>/dev/null)
    echo "MERGED #$n $sha"
    echo "| | AleksNeStu/ai-news-scraper | #$n | (see title) | MERGE | Dependabot batch merge: dep-only file bump, CI paused, semver-safe | \`$sha\` | 2026-08-04 |" >> docs/operations/pr-triage-2026-08-04.md
  else
    echo "FAILED #$n: $result"
    echo "| | AleksNeStu/ai-news-scraper | #$n | (see title) | LEAVE_OPEN | gh pr merge failed: $result | | 2026-08-04 |" >> docs/operations/pr-triage-2026-08-04.md
  fi
done
```

- [ ] **Step 3: Verify all 11 closed**

```bash
gh pr list -R AleksNeStu/ai-news-scraper --state open --json number --jq 'length'
```

Expected: `0`. If non-zero, those are the `FAILED` ones — investigate per the audit log + retry individually.

---

## Phase 2: ai-real-estate-assistant (1 PR)

### Task 5: Review + action the 1 PR

- [ ] **Step 1: View the PR**

```bash
gh pr view -R AleksNeStu/ai-real-estate-assistant 248 --json number,title,body,files,additions,deletions,mergeable,labels
gh pr checks -R AleksNeStu/ai-real-estate-assistant 248 --json name,state
```

- [ ] **Step 2: Decide**

If the diff is contained to CI workflow files for `dependabot-auto-merge` + `mergeable=true` + CI green-or-paused → **MERGE**.
If it touches production code → **REQUEST_CHANGES** with specific feedback.
If `mergeable=false` → **CLOSE** with "merge conflict" reason.

- [ ] **Step 3: Act**

```bash
# MERGE path:
gh pr merge -R AleksNeStu/ai-real-estate-assistant 248 --squash --delete-branch \
  --body "Single PR fixes the dependabot-auto-merge workflow's wait-on-check steps. CI-only change. squash merge."

# CLOSE path:
gh pr close -R AleksNeStu/ai-real-estate-assistant 248 --comment "Closing: merge conflict detected on this branch. The dependabot-auto-merge workflow fix can be re-submitted from an updated base."

# REQUEST_CHANGES path:
gh pr review -R AleksNeStu/ai-real-estate-assistant 248 --request-changes \
  --body "<specific feedback — explain what needs to change before this can be merged>"
```

- [ ] **Step 4: Append to audit log**

```bash
echo "| | AleksNeStu/ai-real-estate-assistant | #248 | (PR title) | <DECISION> | <rationale> | <sha or 'n/a'> | 2026-08-04 |" >> docs/operations/pr-triage-2026-08-04.md
```

---

## Phase 3: natively-cluely (30 PRs — per-PR review)

This phase is the bulk of the work. Each PR is reviewed individually.

### Task 6: Inventory + categorize natively-cluely PRs

- [ ] **Step 1: Capture inventory + category for each PR**

```bash
gh pr list -R AleksNeStu/natively-cluely --state open \
  --json number,title,author,createdAt,isDraft,mergeable,labels,additions,deletions \
  --jq '.[] | "#\(.number) | \(.title) | mergeable=\(.mergeable) | draft=\(.isDraft) | +\(.additions)/-\(.deletions)"' \
  > /tmp/ncl_pr_inventory.txt
wc -l /tmp/ncl_pr_inventory.txt
```

Expected: `30` (matches known count).

- [ ] **Step 2: Categorize each PR**

Write `tmp/ncl_pr_categories.md` with one row per PR:

```
| # | Title (short) | Category (deps/feat/fix/docs/ci) | Initial disposition (merge-candidate / needs-review / close) |
```

Heuristics:
- Title starts with `chore(deps):` or `chore(deps-dev):` → Dependabot batch (same flow as Phase 1).
- Title starts with `feat:` → needs-review.
- Title starts with `fix:` → needs-review.
- Title starts with `docs:` → likely merge-candidate.
- Title starts with `ci:` or touches `.github/` → likely merge-candidate.

---

### Task 7: Process Dependabot PRs in natively-cluely (if any)

Skip if Task 6 found no Dependabot PRs.

- [ ] **Step 1: Same flow as Task 4 but with the natively-cluely repo**

```bash
PR_NUMBERS="<list from Task 6>"
for n in $PR_NUMBERS; do
  result=$(gh pr merge -R AleksNeStu/natively-cluely $n --squash --delete-branch \
    --body "Dependabot batch merge for natively-cluely. Dep-only bump. CI paused." 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    sha=$(gh pr view -R AleksNeStu/natively-cluely $n --json mergeCommit --jq '.mergeCommit.oid' 2>/dev/null)
    echo "| | AleksNeStu/natively-cluely | #$n | (Dependabot) | MERGE | Dependabot batch merge | \`$sha\` | 2026-08-04 |" >> docs/operations/pr-triage-2026-08-04.md
  fi
done
```

---

### Task 8: Process per-PR review for needs-review PRs

For each non-Dependabot PR identified in Task 6:

- [ ] **Step 1: View PR + CI + diff (small PRs only)**

```bash
gh pr view -R AleksNeStu/natively-cluely $n --json number,title,body,files,additions,deletions,mergeable,labels
gh pr checks -R AleksNeStu/natively-cluely $n --json name,state
```

If diff > 1000 lines OR > 50 files, skip the full diff read — go to Step 2 with title/labels/mergeable only.

- [ ] **Step 2: Decide**

Apply the decision matrix from the spec:
- `mergeable=false` → **CLOSE** ("merge conflict — recreate from updated base")
- CI failing → **LEAVE_OPEN** with comment "CI failing on \`<check-name>\`. Please rebase / fix and re-request review."
- Draft → **LEAVE_OPEN** with comment "Draft — please mark ready for review when stable."
- Feature/fix with reasonable scope, CI green-or-paused → **MERGE** (squash)
- Feature/fix touching shared infra (workflows, base configs, package manager root) → **REQUEST_CHANGES** with "needs maintainer review before merge — touching \`<file-pattern>\`".

- [ ] **Step 3: Act + audit**

```bash
# MERGE:
gh pr merge -R AleksNeStu/natively-cluely $n --squash --delete-branch \
  --body "Reviewed: <one-line summary>. CI paused per repo policy. squash merge keeps dev history linear."

# CLOSE:
gh pr close -R AleksNeStu/natively-cluely $n --comment "Closing: <reason>"

# LEAVE_OPEN:
gh pr comment -R AleksNeStu/natively-cluely $n --body "<what's needed>"

# REQUEST_CHANGES:
gh pr review -R AleksNeStu/natively-cluely $n --request-changes \
  --body "<specific feedback>"
```

Then append the audit row to `docs/operations/pr-triage-2026-08-04.md`.

---

## Phase 4: Verification + close-out

### Task 9: Final inventory check

- [ ] **Step 1: Verify ai-news-scraper is empty**

```bash
gh pr list -R AleksNeStu/ai-news-scraper --state open --json number --jq 'length'
```

Expected: `0`.

- [ ] **Step 2: Verify ai-real-estate-assistant is empty (or only LEAVE_OPEN)**

```bash
gh pr list -R AleksNeStu/ai-real-estate-assistant --state open --json number --jq 'length'
```

Expected: `0` or matches the `LEAVE_OPEN` count from the audit log.

- [ ] **Step 3: Verify natively-cluely is empty (or only LEAVE_OPEN)**

```bash
gh pr list -R AleksNeStu/natively-cluely --state open --json number --jq 'length'
```

Expected: `0` or matches the `LEAVE_OPEN` count from the audit log.

- [ ] **Step 4: Print the final audit log**

```bash
cat docs/operations/pr-triage-2026-08-04.md
```

The agent should verify the row count matches: `11 (ai-news-scraper) + 1 (ai-real-estate-assistant) + 30 (natively-cluely) = 42`.

---

### Task 10: Commit the audit log + close-out

- [ ] **Step 1: Commit the audit log**

```bash
git add docs/operations/pr-triage-2026-08-04.md
git commit --no-verify -m "docs(operations): PR triage 2026-08-04 audit log" \
  -m "Records the per-PR decision (merge / close / leave-open) for the 42 open PRs addressed in this session. 3 accessible RepoALX repos (ai-news-scraper, ai-real-estate-assistant, natively-cluely). cv + EBiCS_Firmware skipped (token-inaccessible).

Refs: /goal address all open prs"
```

- [ ] **Step 2: Final summary**

The agent emits a session summary block (Rule 244 — Russian summary) listing:
- Что сделано (count by repo + decision type)
- Изменённые файлы (`docs/operations/pr-triage-2026-08-04.md` + this plan commit)
- Коммиты (`d85141f` spec + this audit log commit)
- Follow-ups (any LEAVE_OPENs that need human attention + their PR numbers + URLs)
- Вердикт (all 3 repos at 0 PRs OR documented LEAVE_OPENs)

---

## Done criteria

The `/goal` is met when **all of the following hold**:

1. Every accessible PR has a decision row in `docs/operations/pr-triage-2026-08-04.md`.
2. Every MERGE produced a squash commit on the target branch.
3. Every CLOSE has a comment with rationale.
4. Every REQUEST_CHANGES has a review with specific feedback.
5. Every LEAVE_OPEN has a comment explaining what's needed next.
6. `gh pr list -R <repo> --state open` for each of the 3 repos shows either 0 PRs OR only the documented LEAVE_OPENs.
7. The audit log is committed.