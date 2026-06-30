#!/usr/bin/env bash
# =====================================================
# AI News Scraper — local verification wrapper
# =====================================================
#
# Windows-friendly bash wrapper around the Makefile targets. Forwards
# all arguments to `make`. Use this when make isn't on PATH or you
# prefer shell scripts.
#
# Examples:
#   ./scripts/check.sh check       # fast gates
#   ./scripts/check.sh test-web    # Next.js build
#   ./scripts/check.sh ci-local    # full CI parity
#   ./scripts/check.sh pre-push    # alias for ci-local
#
# Requires: bash, make (any version)
# =====================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

if ! command -v make >/dev/null 2>&1; then
  echo "error: 'make' not found on PATH. Install make or use the Makefile directly."
  exit 127
fi

if [ $# -eq 0 ]; then
  echo "Usage: $0 <target> [args...]"
  echo ""
  echo "Targets: check | test-api | test-web | ci-local | pre-push"
  exit 1
fi

make "$@"