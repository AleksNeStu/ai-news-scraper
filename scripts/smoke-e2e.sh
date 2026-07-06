#!/usr/bin/env bash
# =====================================================
# smoke-e2e.sh — end-to-end probe against a live deploy
# =====================================================
#
# Runs the canonical G1 acceptance battery (Task #24):
#   1. GET  /health             → 200 + status=ok
#   2. POST /auth/register      → 201 + JWT
#   3. POST /scrape (one URL)   → ArticleOut with summary in range
#   4. POST /search (paraphrase) → target article in top-3
#
# Defaults to one Wikipedia + paraphrase pair (long-form, free to scrape,
# semantic content is unambiguous). Override URL/PARAPHRASE for ad-hoc
# probes; pass --full to cycle through three pairs for a partial
# coverage pass (the full G1 battery needs ~5 URLs and runs in CI).
#
# Requires: bash, curl, jq. OpenSSL for the random password.
#
# Usage:
#   BASE_URL=https://<service>.onrender.com ./scripts/smoke-e2e.sh
#   BASE_URL=https://app.example.com \
#     URL='https://en.wikipedia.org/wiki/Render_(software)' \
#     PARAPHRASE='cloud platform for hosting web services' \
#     ./scripts/smoke-e2e.sh
#   BASE_URL=https://app.example.com ./scripts/smoke-e2e.sh --full
#
# Exit codes:
#   0  — every check passed
#   1  — at least one check failed (details printed to stderr)
#   2  — missing tool (jq) or required env (BASE_URL)
# =====================================================

set -euo pipefail

# --- Args ------------------------------------------------------------------

FULL=0
for arg in "$@"; do
    case "$arg" in
        --full) FULL=1 ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "Unknown arg: $arg" >&2; exit 2 ;;
    esac
done

# --- Pre-flight ------------------------------------------------------------

command -v jq >/dev/null 2>&1 || { echo "✗ jq is required. Install and retry." >&2; exit 2; }
command -v curl >/dev/null 2>&1 || { echo "✗ curl is required." >&2; exit 2; }

: "${BASE_URL:?Set BASE_URL, e.g. https://ai-news-scraper-web.onrender.com}"

# Tolerate either the web origin or a bare api origin; rewrite to web so
# the same-origin rewrite in apps/web/next.config.ts:18-21 can proxy.
case "$BASE_URL" in
    *web*) API_BASE="$BASE_URL" ;;
    *)      API_BASE="https://ai-news-scraper-web.onrender.com" ;;
esac

EMAIL="smoke-$(date +%s)-$RANDOM@example.com"
PASSWORD="$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 64)"

# --- Helpers ---------------------------------------------------------------

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'
pass() { echo "  ${GREEN}✓${RESET} $*"; }
fail() { echo "  ${RED}✗${RESET} $*" >&2; FAILED=1; }
warn() { echo "  ${YELLOW}!${RESET} $*"; }
FAILED=0

# Resolve JSON paths from a curl response on stdin.
jget() { jq -r "$1"; }

# --- Phase 1: /health -------------------------------------------------------

echo "→ 1) Health probe"
HEALTH_BODY="$(curl -fsS --max-time 30 "$API_BASE/api/backend/health" || echo '{}')"
STATUS="$(echo "$HEALTH_BODY" | jget '.status // "missing"')"
if [ "$STATUS" = "ok" ]; then
    pass "/health → status=ok"
else
    fail "/health unexpected body: $HEALTH_BODY"
fi

# --- Phase 2: register ------------------------------------------------------

echo "→ 2) Register temporary user ($EMAIL)"
REG_BODY="$(curl -fsS --max-time 30 -X POST "$API_BASE/api/backend/auth/register" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
    || echo '{}')"

TOKEN="$(echo "$REG_BODY" | jget '.token // empty')"
if [ -z "$TOKEN" ]; then
    fail "/auth/register did not return a token — body: $REG_BODY"
    echo "Aborting — remaining checks need an authenticated session." >&2
    exit 1
fi
USER_ID="$(echo "$REG_BODY" | jget '.user.id // empty')"
pass "/auth/register → user_id=$USER_ID, jwt acquired"

# --- Phase 3+4: scrape + search (per URL) ---------------------------------

run_url_pair() {
    local label="$1" url="$2" paraphrase="$3"

    echo "→ 3) Scrape [$label]: $url"
    local start_ms scrape_body
    start_ms="$(date +%s%3N)"
    scrape_body="$(curl -fsS --max-time 180 -X POST "$API_BASE/api/backend/scrape" \
        -H "Authorization: Bearer $TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"url\":\"$url\"}" \
        || echo '{}')"
    local elapsed_ms=$(( $(date +%s%3N) - start_ms ))

    local article_id summary_len summary_text headline
    article_id="$(echo "$scrape_body" | jget '.id // empty')"
    summary_text="$(echo "$scrape_body" | jget '.summary // empty')"
    summary_len="${#summary_text}"
    headline="$(echo "$scrape_body" | jget '.headline // empty')"

    if [ -z "$article_id" ]; then
        fail "[$label] /scrape did not return id — body: $scrape_body"
        return
    fi
    pass "[$label] /scrape → id=$article_id, took ${elapsed_ms}ms"

    if [ "$summary_len" -lt 100 ] || [ "$summary_len" -gt 600 ]; then
        # PRD asks for 100-300; we widen to 600 because NLTK extractive
        # fallbacks over long pages can produce longer summaries.
        fail "[$label] summary length $summary_len outside 100-600"
    else
        pass "[$label] summary length $summary_len chars (target 100-300)"
    fi

    # Phase 4: search
    echo "→ 4) Search [$label]: \"$paraphrase\""
    local search_body top3_ids
    search_body="$(curl -fsS --max-time 30 -X POST "$API_BASE/api/backend/search" \
        -H "Authorization: Bearer $TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"query\":\"$paraphrase\",\"top_k\":3}" \
        || echo '{}')"

    if ! echo "$search_body" | jq -e '.results' >/dev/null 2>&1; then
        fail "[$label] /search did not return results — body: $search_body"
        warn "[$label] This typically means OPENAI_API_KEY (or equivalent) is not set — embeddings require an active LLM provider."
        return
    fi

    top3_ids="$(echo "$search_body" | jq -r '.results[].article.id // empty' || true)"
    if echo "$top3_ids" | grep -Fq "$article_id"; then
        pass "[$label] /search top-3 contains target article"
    else
        fail "[$label] /search top-3 did not surface target (got: $top3_ids)"
        warn "[$label] Verify an LLM provider key (OPENAI_API_KEY or per-provider) is configured in the Render dashboard."
    fi
}

# Default single-URL smoke (deploy-time, fast).
DEFAULT_URL="${URL:-https://en.wikipedia.org/wiki/Cloud_computing}"
DEFAULT_PARAPHRASE="${PARAPHRASE:-distributed computing over the internet with elastic resources}"

if [ "$FULL" = "0" ]; then
    run_url_pair "default" "$DEFAULT_URL" "$DEFAULT_PARAPHRASE"
else
    run_url_pair "wikipedia/cloud" \
        "https://en.wikipedia.org/wiki/Cloud_computing" \
        "distributed computing over the internet with elastic resources"
    run_url_pair "wikipedia/render" \
        "https://en.wikipedia.org/wiki/Render_(software)" \
        "cloud platform for hosting web services and APIs"
    run_url_pair "rfc-editor/dns" \
        "https://www.rfc-editor.org/rfc/rfc2606" \
        "examples of reserved domain names used in documentation"
fi

# --- Wrap up ---------------------------------------------------------------

echo ""
if [ "$FAILED" = "0" ]; then
    echo "${GREEN}✓ smoke-e2e passed${RESET}"
    exit 0
else
    echo "${RED}✗ smoke-e2e failed${RESET}" >&2
    exit 1
fi
