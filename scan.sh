#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="${BASE_DIR}/config.json"
ENV_FILE="${BASE_DIR}/env.sh"

# Load local secrets if present (KUMA_URL/KUMA_USERNAME/KUMA_PASSWORD)
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

# Load all runtime parameters from config.json
mapfile -t CFG < <(python3 - "$CONFIG_FILE" "$BASE_DIR" <<'PY'
import json, sys
from pathlib import Path
cfg_path=Path(sys.argv[1])
base=Path(sys.argv[2])
cfg=json.loads(cfg_path.read_text())

def out(v):
    print(v)

out(cfg["network_prefix"])
out(cfg["interface"])
out(str(cfg["scan_range_start"]))
out(str(cfg["scan_range_end"]))
out(str(cfg["ping_count"]))
out(str(cfg["ping_timeout_seconds"]))
out(str(cfg["ping_parallelism"]))
out(str(base / cfg["output_json"]))
out(str(base / cfg["output_markdown"]))
out(str(base / cfg["history_file"]))
out(cfg["version"])
PY
)

NETWORK_PREFIX="${CFG[0]}"
IFACE="${CFG[1]}"
SCAN_START="${CFG[2]}"
SCAN_END="${CFG[3]}"
PING_COUNT="${CFG[4]}"
PING_TIMEOUT_SECONDS="${CFG[5]}"
PING_PARALLELISM="${CFG[6]}"
OUT_JSON="${CFG[7]}"
OUT_MD="${CFG[8]}"
HISTORY_JSON="${CFG[9]}"
VERSION="${CFG[10]}"

# 1) Ping sweep to populate ARP/neigh cache
seq "$SCAN_START" "$SCAN_END" | xargs -I{} -P "$PING_PARALLELISM" sh -c \
  "ping -c '$PING_COUNT' -W '$PING_TIMEOUT_SECONDS' '${NETWORK_PREFIX}.{}' >/dev/null 2>&1 || true"

# 2) Build enriched JSON + Markdown + vault exports
export IFACE NETWORK_PREFIX OUT_JSON OUT_MD HISTORY_JSON VERSION
uv run "${BASE_DIR}/scan.py"

echo "Wrote ${OUT_JSON}"
echo "Wrote ${OUT_MD}"
