#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${BASE_DIR}/env.sh"

# Load local secrets if present (KUMA_URL/KUMA_USERNAME/KUMA_PASSWORD)
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

uv run "${BASE_DIR}/scan.py"
