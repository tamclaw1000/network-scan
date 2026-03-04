#!/usr/bin/env bash
set -euo pipefail

NETWORK_PREFIX="192.168.1"
IFACE="eth0"
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_JSON="${BASE_DIR}/devices.json"
OUT_MD="${BASE_DIR}/devices.md"
HISTORY_JSON="${BASE_DIR}/.scan_history.json"
VERSION="v00.01.00"

# 1) Ping sweep to populate ARP/neigh cache
seq 1 254 | xargs -I{} -P 64 sh -c "ping -c 1 -W 1 ${NETWORK_PREFIX}.{} >/dev/null 2>&1 || true"

# 2) Build enriched JSON + Markdown
export IFACE NETWORK_PREFIX OUT_JSON OUT_MD HISTORY_JSON VERSION
python3 "${BASE_DIR}/scan.py"

echo "Wrote ${OUT_JSON}"
echo "Wrote ${OUT_MD}"
