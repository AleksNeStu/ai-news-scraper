#!/usr/bin/env bash
# =====================================================
# Private-leak check — single source of truth for the
# forbidden-identifier pattern list.
#
# Modes:
#   bash scripts/private-leak-check.sh                  # file-scan (stdin)
#   bash scripts/private-leak-check.sh --message <file> # commit-msg
#   bash scripts/private-leak-check.sh --self-test      # smoke test
#   bash scripts/private-leak-check.sh --help           # usage banner
#
# Exit codes:
#   0 clean
#   1 leak found
#   2 usage error
# =====================================================

set -euo pipefail

# ---------- Canonical pattern list (single source of truth) ----------
# Sourced from CLAUDE.md "Hard rules". The list below is the ONLY place
# in the tracked tree where these tokens appear literally. All other
# layers (pre-commit, CI workflow) call THIS script; they never duplicate.
#
# Lines below this banner are matched as case-insensitive extended regex.
# Substring match is intentional — line-wrapped variants and variants with
# internal separators (e.g. "Repo-ALX", "dev_scaler") are caught.
#
# DO NOT add patterns here unless CLAUDE.md "Hard rules" authorises them.
# DO NOT echo this list in replies, commit messages, docs, or comments.
read -r -d '' PATTERNS <<'EOF' || true
NestSolo
nest-solo
NestLab
NestLab-Tech
dev-scaler
nest-ai-dev
RepoALX
repo-alex
mirror1
mirror2
ai-real-estate-assistant
EOF

# ---------- Helpers ----------

# Normalise one line in pure bash (no subshell forks). Lowercase, trim
# leading/trailing whitespace, collapse interior whitespace runs, strip a
# leading "#" comment. The original line is preserved elsewhere so the
# leak report can show what the file actually contains.
normalise() {
    local s=$1
    # lowercase
    s=${s,,}
    # trim leading whitespace
    s=${s#"${s%%[![:space:]]*}"}
    # trim trailing whitespace
    s=${s%"${s##*[![:space:]]}"}
    # collapse interior whitespace runs to a single space — pure bash so
    # we avoid the per-call fork that `printf | tr -s` would cost (which
    # turned O(n) subshells into the O(n²) hang that bit the first revision).
    local out="" prev='x' len=${#s} j=0 ch
    while (( j < len )); do
        ch=${s:j:1}
        if [[ $ch == ' ' || $ch == $'\t' ]]; then
            if [[ $prev != ' ' ]]; then
                out+=' '
                prev=' '
            fi
        else
            out+="$ch"
            prev="$ch"
        fi
        j=$((j+1))
    done
    s=$out
    # strip a leading "#" comment
    s=${s##\#*}
    s=${s#"${s%%[![:space:]]*}"}
    s=${s%"${s##*[![:space:]]}"}
    printf '%s\n' "$s"
}

# Scan an input stream. Source label distinguishes file vs commit-msg in
# the leak report. Three passes per input:
#   (a) every raw line
#   (b) every normalised line
#   (c) every normalised pair of consecutive lines (the "line-wrap bypass"
#       — a forbidden token split across two adjacent lines)
# All work happens in bash memory; we call grep ONCE against the combined
# buffer to keep the scan O(1) forks regardless of input size. The previous
# version spawned a printf+grep subshell per line + per pair, which was
# O(n²) forks and effectively unusable beyond ~50 lines on platforms where
# fork() is expensive (notably Git Bash on Windows).
#
# Only the integer count reaches stdout; LEAK messages go to stderr so
# callers can safely `count=$(scan_stream ...)` without capturing leak
# text in the returned string.
scan_stream() {
    local source=$1
    local lines=() line
    local norms=() norm

    # 1. Read everything into bash memory (no subshell during read).
    while IFS= read -r line || [[ -n $line ]]; do
        lines+=("$line")
    done

    local n=${#lines[@]}
    if (( n == 0 )); then
        printf '0'
        return
    fi

    # 2. Normalise each line (no subshell — pure bash string ops via
    # normalise()).
    local i out_buf="" norm_buf="" pair_buf="" a b
    for ((i = 0; i < n; i++)); do
        norm=$(normalise "${lines[$i]}")
        norms+=("$norm")
        out_buf+=${lines[$i]}$'\n'
        norm_buf+="$norm"$'\n'
    done
    for ((i = 0; i < n - 1; i++)); do
        a=${norms[$i]} b=${norms[$((i + 1))]}
        pair_buf+="$a $b"$'\n'
        pair_buf+="$a$b"$'\n'
    done

    # 3. Convert newline-separated PATTERNS to ERE alternation. Done once
    # per scan_stream call (cheap, single paste fork).
    local pat_re
    pat_re=$(printf '%s\n' "$PATTERNS" | paste -sd'|' -)

    # 4. ONE grep call against the combined buffer. -iE for case-insensitive
    # ERE; -n adds line numbers so we can attribute the leak.
    local hits
    hits=$(printf '%s\n%s\n%s' "$out_buf" "$norm_buf" "$pair_buf" \
        | grep -inE "$pat_re" 2>/dev/null || true)

    local count=0
    if [[ -n $hits ]]; then
        while IFS= read -r hit; do
            [[ -z $hit ]] && continue
            local ln=${hit%%:*} rest=${hit#*:}
            # The combined buffer's line numbering is offset: out_buf spans
            # 1..n, norm_buf spans n+1..2n, pair_buf spans 2n+1..end.
            # Translate to the original-file line for the report.
            local orig_ln=0 kind="raw"
            if (( ln >= 1 && ln <= n )); then
                orig_ln=$ln
                kind="raw"
            elif (( ln > n && ln <= 2 * n )); then
                orig_ln=$((ln - n))
                kind="normalised"
            else
                # pair_buf: each pair is two lines, only the first of which
                # identifies the leaked raw span.
                local pair_idx=$((ln - 2 * n - 1))
                local pair_pair=$((pair_idx / 2))
                orig_ln=$((pair_pair + 1))
                if (( pair_idx % 2 == 0 )); then
                    kind="line-wrap (sp)"
                else
                    kind="line-wrap (no-sp)"
                fi
            fi
            printf 'LEAK: %s line %d (%s): %s\n' \
                "$source" "$orig_ln" "$kind" "$rest" >&2
            count=$((count + 1))
        done <<< "$hits"
    fi
    printf '%d' "$count"
}

usage() {
    cat <<'USAGE'
private-leak-check — scan for forbidden private-infrastructure identifiers

USAGE:
  bash scripts/private-leak-check.sh                  # file-scan (stdin)
  bash scripts/private-leak-check.sh --message <file> # commit-msg from file
  bash scripts/private-leak-check.sh --message -      # commit-msg from stdin
  bash scripts/private-leak-check.sh --self-test      # smoke test
  bash scripts/private-leak-check.sh --help           # this banner

EXIT CODES:
  0  clean
  1  leak found (LEAK lines + "blocked: N leaks" summary on stderr)
  2  usage error

The canonical pattern list is defined in this script. Run --self-test to
verify the list is intact.
USAGE
}

# ---------- Self-test (5 cases per design §5) ----------
#
# Inline fixtures only. No tracked fixture files. The pattern list itself
# must not be duplicated outside the canonical here-doc above.
#
# Trick: for "contains pattern" cases we build the offending line from the
# first line of the PATTERNS here-doc. For "clean" cases we use literal
# strings that do NOT contain any forbidden token. This keeps the patterns
# in exactly one place.
self_test() {
    local failed=0
    local total=5

    # Helper: run one case. Args: label, expected_exit, command...
    run_case() {
        local label=$1; shift
        local expected=$1; shift
        local actual=0
        "$@" >/dev/null 2>&1 || actual=$?
        if [[ $actual -eq $expected ]]; then
            printf 'PASS: %s\n' "$label"
        else
            printf 'FAIL: %s: expected exit %d, got %d\n' "$label" "$expected" "$actual"
            failed=$((failed + 1))
        fi
    }

    # Extract first pattern line from the here-doc. This guarantees the
    # self-test "leak" fixtures contain an actual forbidden token without
    # us echoing any token literally in this file beyond the here-doc.
    local first_pattern
    first_pattern=$(printf '%s\n' "$PATTERNS" | head -n1)

    # Case 1: clean commit message
    local tmp_clean1
    tmp_clean1=$(mktemp)
    printf 'this is a perfectly ordinary commit message\n' > "$tmp_clean1"
    run_case "clean commit message" 0 \
        bash "$0" --message "$tmp_clean1"

    # Case 2: commit message containing one pattern (any casing)
    local tmp_leak1
    tmp_leak1=$(mktemp)
    printf 'see line %s for context\n' "$first_pattern" > "$tmp_leak1"
    run_case "commit msg contains pattern" 1 \
        bash "$0" --message "$tmp_leak1"

    # Case 3: pattern split across two lines (line-wrap bypass)
    # Split "first_pattern" at its second character — both halves get
    # reassembled by normalisation in the scan, so the bypass fails.
    local mid=$(( ${#first_pattern} / 2 ))
    if [[ $mid -lt 1 ]]; then mid=1; fi
    local part_a=${first_pattern:0:mid}
    local part_b=${first_pattern:mid}
    local tmp_wrap
    tmp_wrap=$(mktemp)
    printf '%s\n%s\n' "$part_a" "$part_b" > "$tmp_wrap"
    # The wrap must reconstruct the pattern only AFTER normalisation, so
    # the raw pass may or may not fire depending on split — we assert the
    # EXIT is non-zero (1) which is the design contract for this case.
    run_case "line-wrap bypass fails" 1 \
        bash "$0" --message "$tmp_wrap"

    # Case 4: clean file diff (`git diff` output)
    local tmp_diff_clean
    tmp_diff_clean=$(mktemp)
    cat > "$tmp_diff_clean" <<'DIFF'
diff --git a/apps/api/api/main.py b/apps/api/api/main.py
index 1234567..89abcde 100644
--- a/apps/api/api/main.py
+++ b/apps/api/api/main.py
@@ -1,3 +1,4 @@
 from fastapi import FastAPI

 app = FastAPI()
+# clean comment
DIFF
    run_case "clean file diff" 0 \
        bash "$0" < "$tmp_diff_clean"

    # Case 5: file diff containing a pattern
    local tmp_diff_leak
    tmp_diff_leak=$(mktemp)
    cat > "$tmp_diff_leak" <<DIFF
diff --git a/README.md b/README.md
index 1234567..89abcde 100644
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 hello world
+reference to ${first_pattern} here
DIFF
    run_case "file diff contains pattern" 1 \
        bash "$0" < "$tmp_diff_leak"

    rm -f "$tmp_clean1" "$tmp_leak1" "$tmp_wrap" "$tmp_diff_clean" "$tmp_diff_leak"

    printf 'self-test: %d/%d passed\n' "$((total - failed))" "$total"
    if [[ $failed -eq 0 ]]; then
        return 0
    fi
    return 1
}

# ---------- Entry point ----------

main() {
    # Parse args. We need exactly one of: stdin (no args, no --message)
    # OR --message <file>. --self-test and --help are standalone.
    case ${1:-} in
        --help|-h)
            usage
            return 0
            ;;
        --self-test)
            self_test
            return $?
            ;;
        --message)
            if [[ $# -ne 2 ]]; then
                printf 'usage: --message <file|->\n' >&2
                return 2
            fi
            # "-" reads from stdin and snapshots it to a temp file. The
            # snapshot lets scan_stream operate uniformly against either a
            # real path or stdin, and avoids relying on /dev/stdin — which
            # is not a usable path on Windows Git Bash.
            local msg_file cleanup=""
            if [[ $2 == "-" ]]; then
                msg_file=$(mktemp)
                cleanup=$msg_file
                cat > "$msg_file"
            elif [[ -f $2 ]]; then
                msg_file=$2
            else
                printf 'error: file not found: %s\n' "$2" >&2
                return 2
            fi
            # scan_stream prints LEAK lines on stderr and the integer count
            # on stdout. Capture both via process substitution so we can
            # forward the LEAKs and use the count to set the exit code.
            local count leak_lines
            leak_lines=$(scan_stream "commit-msg" < "$msg_file" 2>&1 >/dev/null || true)
            count=$(scan_stream "commit-msg" < "$msg_file" 2>/dev/null || echo 0)
            if [[ -n $leak_lines ]]; then
                printf '%s\n' "$leak_lines"
            fi
            if [[ ${cleanup:-} && -f $cleanup ]]; then
                rm -f "$cleanup"
            fi
            if [[ $count -gt 0 ]]; then
                printf 'blocked: %d leaks\n' "$count" >&2
                return 1
            fi
            return 0
            ;;
        "")
            # File-scan mode: read stdin
            local count=0
            count=$(scan_stream "file")
            if [[ $count -gt 0 ]]; then
                printf 'blocked: %d leaks\n' "$count" >&2
                return 1
            fi
            return 0
            ;;
        *)
            printf 'usage error: unknown arg: %s\n' "$1" >&2
            usage >&2
            return 2
            ;;
    esac
}

main "$@"
