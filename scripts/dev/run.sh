#!/usr/bin/env bash
# =====================================================
# AI News Scraper — local dev launcher (Linux/macOS)
# =====================================================
# Brings the full stack up via docker compose: Postgres, Redis,
# ChromaDB, the one-shot Alembic + seed migration, the FastAPI app,
# and the Next.js web UI. After the stack reports healthy, prints
# the URLs the user should open.
#
# Usage:
#   bash scripts/dev/run.sh           # app stack only
#   bash scripts/dev/run.sh --monitor # also bring up Uptime Kuma
#   bash scripts/dev/run.sh --logs    # then tail logs (Ctrl-C to exit)
#   bash scripts/dev/run.sh --help
#
# Stop with:  bash scripts/dev/stop.sh
# Logs with:  bash scripts/dev/logs.sh
# Status:     bash scripts/dev/status.sh
# =====================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

WITH_MONITOR=0
WITH_LOGS=0

for arg in "$@"; do
  case "$arg" in
    --monitor|-m) WITH_MONITOR=1 ;;
    --logs|-f)    WITH_LOGS=1 ;;
    --help|-h)
      sed -n '3,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 2
      ;;
  esac
done

# ---- preflight ----
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: docker daemon not running. Start Docker Desktop and retry." >&2
  exit 1
fi

COMPOSE_FILES=(-f docker-compose.yml)
if [[ "$WITH_MONITOR" -eq 1 ]]; then
  COMPOSE_FILES+=(-f docker-compose.monitoring.yml)
fi

echo "=== AI News Scraper — local dev ==="
echo "Project root: $PROJECT_ROOT"
echo "Compose files: ${COMPOSE_FILES[*]}"
echo

# ---- bring stack up ----
echo "[1/3] docker compose up -d ..."
docker compose "${COMPOSE_FILES[@]}" up -d --build

# ---- wait for health ----
echo "[2/3] waiting for api + web healthchecks ..."
ATTEMPTS=60
for svc in ai-news-api ai-news-web; do
  for i in $(seq 1 $ATTEMPTS); do
    STATE=$(docker inspect --format='{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "missing")
    if [[ "$STATE" == "healthy" ]]; then
      echo "  $svc: healthy"
      break
    fi
    if [[ "$i" -eq $ATTEMPTS ]]; then
      echo "  $svc: not healthy after $ATTEMPTS attempts (state=$STATE)" >&2
      echo "  hint: bash scripts/dev/logs.sh $svc" >&2
      exit 1
    fi
    sleep 2
  done
done

# ---- show URLs ----
echo "[3/3] ready"
echo
echo "  Web UI:  http://localhost:3000"
echo "  API:     http://localhost:8082"
echo "  API doc: http://localhost:8082/docs"
if [[ "$WITH_MONITOR" -eq 1 ]]; then
  echo "  Kuma:    http://127.0.0.1:3001 (deploy-host only)"
fi
echo "  Login:   alex@example.com / dev-only-do-not-use-in-prod"
echo
echo "  bash scripts/dev/stop.sh   # stop stack"
echo "  bash scripts/dev/logs.sh  # tail logs"
echo

if [[ "$WITH_LOGS" -eq 1 ]]; then
  exec bash "$SCRIPT_DIR/logs.sh"
fi