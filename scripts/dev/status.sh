#!/usr/bin/env bash
# =====================================================
# AI News Scraper — show stack status (Linux/macOS)
# =====================================================
# One-shot snapshot of running containers, health states,
# and the ports the user can hit.
# =====================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

COMPOSE_FILES=(-f docker-compose.yml)
[[ -f docker-compose.monitoring.yml ]] && COMPOSE_FILES+=(-f docker-compose.monitoring.yml)

echo "=== containers ==="
docker compose "${COMPOSE_FILES[@]}" ps
echo
echo "=== health states ==="
docker ps --filter "name=ai-news-" --format '{{.Names}}\t{{.Status}}' | column -t -s $'\t' || true
echo
echo "=== urls (when healthy) ==="
echo "  Web UI:  http://localhost:3000"
echo "  API:     http://localhost:8082"
echo "  API doc: http://localhost:8082/docs"