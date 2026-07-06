#!/usr/bin/env bash
# =====================================================
# gen-prod-env.sh — mint a production-shaped .env (local-parity)
# =====================================================
#
# Reads .env.example, validates production-critical vars, prompts for
# the values that must be unique to prod (JWT secrets, CORS, SMTP,
# provider keys, ...), and writes a chmod 600 file.
#
# Usage:
#   ./scripts/gen-prod-env.sh              # writes .env.production
#   ./scripts/gen-prod-env.sh .env.staging # writes .env.staging
#
# The output file is NEVER committed (.env* is gitignored).
#
# IMPORTANT: this script is now a LOCAL-PARITY mint, not the runtime
# source-of-truth for production. On Render, secrets live in the
# dashboard's per-service "sync: false" entries (see render.yaml and
# docs/operations/deploy.md §2). Use the values minted here as the
# inputs to paste into the Render dashboard.
# =====================================================

set -euo pipefail

OUT="${1:-.env.production}"
EXAMPLE=".env.example"

# --- Pre-flight -----------------------------------------------------------

[ -f "$EXAMPLE" ] || { echo "✗ $EXAMPLE not found — run from the repo root." >&2; exit 1; }
if [ -e "$OUT" ]; then
    read -rp "→ $OUT already exists. Overwrite? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { echo "Aborted." >&2; exit 1; }
fi

# --- Var metadata ---------------------------------------------------------
#
# REQUIRED_PROD: must be non-empty in prod. Script prompts and refuses to
# accept the .env.example placeholder.
#
# OPTIONAL:  prompted with a default (left empty if user hits Enter).
#
# KNOWN_PLACEHOLDERS: rejected outright when offered as the value.

KNOWN_PLACEHOLDERS=(
    "sk-replace-me"
    "change-me-in-production"
    "change-me-in-production-use-a-long-random-string"
    "dev-secret-change-me"
    "dev-unsubscribe-secret-change-me"
)

# Vars that must be set to a real value (no placeholder, no empty).
# key=PROMPT_TEXT
declare -A REQUIRED_PROD=(
    ["APP_ENV"]="APP_ENV (production|staging) [production]"
    ["JWT_SECRET"]="JWT_SECRET (64+ char random — openssl rand -hex 32)"
    ["UNSUBSCRIBE_JWT_SECRET"]="UNSUBSCRIBE_JWT_SECRET (different from JWT_SECRET, 64+ chars)"
    ["CORS_ALLOW_ORIGINS"]='CORS_ALLOW_ORIGINS (JSON list, must include https:// for prod) e.g. ["https://app.your-domain.com"]'
    ["DATABASE_URL"]="DATABASE_URL (asyncpg URL — INTERNAL compose URL is fine)"
    ["DATABASE_URL_SYNC"]="DATABASE_URL_SYNC (psycopg URL, same host)"
    ["CHROMA_HOST"]="CHROMA_HOST (container DNS name; usually 'chromadb')"
    ["REDIS_URL"]="REDIS_URL (container DNS name; usually redis://redis:6379/0)"
)

# Vars prompted but allow empty (features that are off until you turn them on).
declare -A OPTIONAL_PROD=(
    ["OPENAI_API_KEY"]="OPENAI_API_KEY (sk-...; required for AI brief — leave empty for NLTK-only mode)"
    ["DEEPSEEK_API_KEY"]="DEEPSEEK_API_KEY (if LLM_PROVIDER=deepseek)"
    ["GEMINI_API_KEY"]="GEMINI_API_KEY (if LLM_PROVIDER=gemini)"
    ["GOOGLE_API_KEY"]="GOOGLE_API_KEY (mirror of GEMINI_API_KEY)"
    ["OPENROUTER_API_KEY"]="OPENROUTER_API_KEY (if LLM_PROVIDER=openrouter)"
    ["LLM_PROVIDER"]="LLM_PROVIDER [deepseek]"
    ["SMTP_HOST"]="SMTP_HOST (blank = digest email disabled)"
    ["SMTP_PORT"]="SMTP_PORT [587]"
    ["SMTP_USER"]="SMTP_USER"
    ["SMTP_PASSWORD"]="SMTP_PASSWORD"
    ["SMTP_FROM"]="SMTP_FROM (full address)"
)

# --- Helpers --------------------------------------------------------------

is_placeholder() {
    local val="$1"
    for ph in "${KNOWN_PLACEHOLDERS[@]}"; do
        if [ "$val" = "$ph" ]; then return 0; fi
    done
    return 1
}

# --- Collect prompts up-front so the operator can prepare ---------------
echo "→ Generating $OUT"
echo "  (Required vars will be prompted; optional vars accept Enter to leave empty.)"
echo ""

# Pre-flight: APP_ENV must be production or staging.
APP_ENV_VAL=""
while true; do
    read -rp "  APP_ENV [production]: " APP_ENV_VAL
    APP_ENV_VAL="${APP_ENV_VAL:-production}"
    case "$APP_ENV_VAL" in
        production|staging) break ;;
        *) echo "  ✗ APP_ENV must be 'production' or 'staging'." ;;
    esac
done

# --- Collect values for required vars ------------------------------------

declare -A VALUES
for key in "${!REQUIRED_PROD[@]}"; do
    prompt="${REQUIRED_PROD[$key]}"
    if [ "$key" = "APP_ENV" ]; then
        VALUES["$key"]="$APP_ENV_VAL"
        continue
    fi
    while true; do
        if [ "$key" = "CORS_ALLOW_ORIGINS" ] && [ "$APP_ENV_VAL" = "production" ]; then
            read -rp "  $prompt: " v
            if ! echo "$v" | grep -q "https://"; then
                echo "  ✗ Production CORS_ALLOW_ORIGINS must include at least one https:// origin." >&2
                continue
            fi
        else
            # Hide secret values on screen (best-effort via stty).
            if [[ "$key" == *SECRET* || "$key" == *PASSWORD* || "$key" == *_KEY ]]; then
                read -rsp "  $prompt: " v; echo
            else
                read -rp "  $prompt: " v
            fi
        fi
        [ -n "$v" ] || { echo "  ✗ $key cannot be empty." >&2; continue; }
        if is_placeholder "$v"; then
            echo "  ✗ $key is the dev placeholder — set a real value." >&2
            continue
        fi
        VALUES["$key"]="$v"
        break
    done
done

# --- Optional vars --------------------------------------------------------

for key in "${!OPTIONAL_PROD[@]}"; do
    prompt="${OPTIONAL_PROD[$key]}"
    if [[ "$key" == *SECRET* || "$key" == *PASSWORD* || "$key" == *_KEY ]]; then
        read -rsp "  $prompt (blank to skip): " v; echo
    else
        read -rp "  $prompt (blank to skip): " v
    fi
    [ -n "$v" ] && VALUES["$key"]="$v"
done

# --- Walk the .env.example, emit line-by-line ----------------------------
#
# For each line in .env.example:
#   - blank or '#' comment   -> echo as-is
#   - KEY=... with KEY in VALUES -> emit VALUES[KEY]
#   - KEY=... not in VALUES -> emit the example line as-is
#     (preserves defaults for LOG_LEVEL, JWT_ALGORITHM, etc.)

touch "$OUT"
chmod 600 "$OUT"

while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        ''|\#*) echo "$line" >> "$OUT" ;;
        *=*)
            key="${line%%=*}"
            if [ -n "${VALUES[$key]+set}" ]; then
                echo "$key=${VALUES[$key]}" >> "$OUT"
            else
                echo "$line" >> "$OUT"
            fi
            ;;
        *) echo "$line" >> "$OUT" ;;
    esac
done < "$EXAMPLE"

echo ""
echo "✓ Wrote $OUT (chmod 600). Review before docker compose up."
echo "  diff $EXAMPLE $OUT  # sanity-check overrides"
echo "  grep -E '^(JWT_SECRET|UNSUBSCRIBE_JWT_SECRET|APP_ENV)' $OUT"
