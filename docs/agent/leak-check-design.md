# Leak-check enforcement — design contract

One-page design for the three layers that enforce the "no private-infra
identifiers in tracked files or commit messages" rule (see CLAUDE.md Hard rules).

The canonical pattern list lives **only** in `scripts/private-leak-check.sh`.
All other layers invoke that script; they never redefine the list.

---

## 1. Script contract — `scripts/private-leak-check.sh`

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | clean — no leaks in the input |
| `1`  | leak found — print offending lines and bail |
| `2`  | usage error — bad arguments |

### Invocation modes

```
bash scripts/private-leak-check.sh                    # file-scan mode (reads stdin)
bash scripts/private-leak-check.sh --message <file>   # commit-msg mode (reads file)
bash scripts/private-leak-check.sh --self-test        # smoke test — exits 0 if patterns are sane, 1 if not
bash scripts/private-leak-check.sh --help             # usage banner to stdout
```

Exactly one of `stdin` (file-scan) or `--message <file>` (commit-msg) is required.
Anything else → exit `2`.

### Pre-conditions

- `set -euo pipefail` at the top.
- Bash 4+ on `ubuntu-latest` GitHub runner AND Git Bash on Windows. Avoid
  BSD-only `stat -f`; prefer `case` fall-through and `[[ ]]` for tests.
- The pattern list is sourced at script start from the canonical list in
  CLAUDE.md "Hard rules". The script embeds that list **exactly once** via
  a here-doc, then loops over it. The list itself is gitignored-by-convention
  inside the script (never echoed, never duplicated elsewhere).
- Output format on leak: each offending line is prefixed with `LEAK: ` and
  the source (`file` for stdin mode, `commit-msg` for `--message` mode). A
  final summary line `blocked: N leaks` is printed to stderr; exit `1`.

### Normalisation rules (applied before pattern match)

The script must normalise every input line to defeat trivial bypass:

1. Lowercase the whole line.
2. Strip leading and trailing whitespace per line.
3. Collapse internal whitespace runs (spaces, tabs) to a single space.
4. Strip line comments — a line beginning with `#` after steps 1–3 is dropped.

This is the trap that bit the project before: a pattern split across two lines
or embedded in a `#` comment would otherwise pass.

### Pattern handling

The script must:

- Treat every pattern as a case-insensitive extended regex (`grep -iE`).
- Anchor patterns loosely (substring match, not word-boundary) so that
  line-wrapped variants and variants with separators are caught.
- Match on the **original** AND the **normalised** form of every input line.
- Test both file-scan and commit-msg modes in `--self-test` (see §5).

---

## 2. Pre-commit hook contract — `.pre-commit-config.yaml`

The existing config (`pre-commit` stage) is **not** modified. A new
`commit-msg` stage is added as a sibling entry:

```yaml
- id: leak-check-msg
  name: private-lera-check (commit-msg)         # placeholder, see note below
  stages: [commit-msg]
  entry: bash scripts/private-leak-check.sh --message
  language: system
  pass_filenames: false
  always_run: true
```

Notes for Backend:

- `pre-commit` framework invokes `entry` with the commit-msg file path
  appended as a positional argument; `--message` consumes it.
- `pass_filenames: false` is the safest default here (the script reads the
  file directly, not the staged content).
- `always_run: true` ensures the hook fires even when no file is staged
  (e.g. an empty `git commit --allow-empty`).
- Stdout/stderr from the script is surfaced to the user by the framework.
- Add the matching `pre-commit` stage entry that scans staged files via
  the same script in file-scan mode (`git diff --cached | bash ...`).
  The existing config has no such entry — this is the other missing piece.

---

## 3. CI workflow contract — `.github/workflows/private-leak-check.yml`

### Triggers

```yaml
on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]
  workflow_dispatch: {}
```

Branch coverage mirrors `.github/workflows/ci.yml` so the two workflows
agree on what they gate.

### Permissions and concurrency

```yaml
permissions:
  contents: read   # explicit; no write, no admin

concurrency:
  group: leak-${{ github.ref }}
  cancel-in-progress: true
```

Read-only token; the workflow only checks, never mutates. Concurrency
group is per-ref so a fast-follow push doesn't queue behind an older run.

### Jobs (single `scan` job, ubuntu-latest)

```yaml
jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v7
        with: { fetch-depth: 0 }   # need full history for the range scan
      - name: scan tracked files
        run: |
          git ls-files -z | xargs -0 cat \
            | bash scripts/private-leak-check.sh
      - name: scan commit messages (push)
        if: github.event_name == 'push'
        run: |
          BEFORE="${{ github.event.before }}"
          AFTER="${{ github.sha }}"
          git log "${BEFORE}..${AFTER}" --format=%B \
            | bash scripts/private-leak-check.sh --message /dev/stdin
      - name: scan commit messages (pull_request)
        if: github.event_name == 'pull_request'
        run: |
          BASE="${{ github.event.pull_request.base.sha }}"
          HEAD="${{ github.event.pull_request.head.sha }}"
          git log "${BASE}..${HEAD}" --format=%B \
            | bash scripts/private-leak-check.sh --message /dev/stdin
```

Two passes per run, matching CLAUDE.md: tracked file content AND every commit
message in the push / PR range. The PR-pass only fires on `pull_request`;
the push-pass only fires on `push` — the workflow handles both event kinds.

Token: `${{ secrets.GITHUB_TOKEN }}` (auto-provisioned by GitHub Actions;
no new secret required).

---

## 4. CLAUDE.md sync contract (Backend's L4)

Backend's L4 must:

- Keep the rule text in the "Hard rules" section.
- Replace any embedded pattern list with a single line:

  > The forbidden identifier list is defined in
  > `scripts/private-leak-check.sh` (single source of truth).
  > Run `bash scripts/private-leak-check.sh --help` to see usage.

- Add a one-sentence note that the rule is enforced by:
  - the `pre-commit` and `commit-msg` hooks in `.pre-commit-config.yaml`
    (calls the script in file-scan and `--message` modes respectively), and
  - the `.github/workflows/private-leak-check.yml` CI workflow (scans both
    tracked files and commit-message bodies in the push / PR range).

No pattern examples, no sibling-repo names, no org names appear in CLAUDE.md
after the sync.

---

## 5. Self-test fixtures (Backend's `--self-test`)

`bash scripts/private-leak-check.sh --self-test` must verify all five cases
below and exit `0` only if every expected result matches:

| Case | Input                                | Expected exit |
|------|--------------------------------------|---------------|
| 1    | clean commit message                 | `0`           |
| 2    | commit message containing one pattern (any casing) | `1` |
| 3    | commit message with the pattern split across two lines (line-wrap bypass) | `1` |
| 4    | clean file diff (`git diff` output)  | `0`           |
| 5    | file diff containing a pattern       | `1`           |

Fixtures live inside the script as inline strings (no tracked fixture
files — the pattern list itself must not be duplicated). The `--self-test`
mode prints `PASS: <case-name>` for each pass and `FAIL: <case-name>: <reason>`
for each fail.

---

## 6. Single-source-of-truth invariant

The pattern list must appear in exactly one place in the entire tracked
tree: the here-doc inside `scripts/private-leak-check.sh`. Concretely:

- CLAUDE.md references the script by path; never lists patterns inline.
- `.pre-commit-config.yaml` calls the script by name; never lists patterns.
- `.github/workflows/private-leak-check.yml` runs the script; never lists patterns.
- No design doc, ADRs, README, or commit message echoes patterns literally.
- If a future rule change requires a new pattern, the change touches ONLY
  the script's here-doc; everything else stays as-is.

If a second location is ever needed (e.g. for a separate Windows-only hook),
that location must `source` the script's here-doc, not duplicate it.
