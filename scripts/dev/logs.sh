#!/usr/bin/env bash
# =====================================================
# AI News Scraper — tail logs (Linux/macOS)
# =====================================================
# Tails docker compose logs. Pass a service name (or partial) to
# filter. Examples:
#   bash scripts/dev/logs.sh              # all services
#   bash scripts/dev/logs.sh api          # just the API
#   bash scripts/dev/logs.sh api web      # API + web
#   bash scripts/dev/logs.sh --since 5m   # last 5 minutes
# =====================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

COMPOSE_FILES=(-f docker-compose.yml)
if [[ -f docker-compose.monitoring.yml ]]; then
  COMPOSE_FILES+=(-f docker-compose.monitoring.yml)
fi

docker compose "${COMPOSE_FILES[@]}" logs -f "$@"