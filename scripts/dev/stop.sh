#!/usr/bin/env bash
# =====================================================
# AI News Scraper — stop local stack (Linux/macOS)
# =====================================================
# Brings the dev stack down. Use --volumes to also wipe the
# Postgres / Redis / ChromaDB named volumes (destructive).
# =====================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

WITH_VOLUMES=0
WITH_MONITOR=0
for arg in "$@"; do
  case "$arg" in
    --volumes|-v) WITH_VOLUMES=1 ;;
    --monitor|-m) WITH_MONITOR=1 ;;
    --help|-h)
      sed -n '3,10p' "$0"
      exit 0
      ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

COMPOSE_FILES=(-f docker-compose.yml)
[[ "$WITH_MONITOR" -eq 1 ]] && COMPOSE_FILES+=(-f docker-compose.monitoring.yml)

echo "=== AI News Scraper — stop stack ==="
if [[ "$WITH_VOLUMES" -eq 1 ]]; then
  echo "WARNING: --volumes will wipe pgdata / redisdata / chromadata"
  docker compose "${COMPOSE_FILES[@]}" down --volumes
else
  docker compose "${COMPOSE_FILES[@]}" down
fi
echo "done."