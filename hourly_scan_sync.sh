#!/usr/bin/env bash
set -euo pipefail

SCAN_DIR="/home/tamclaw/.openclaw/workspace-darren/projects/homenetwork/scan"
HOSTNAME="$(hostname)"
RUNTIME_DIR="$SCAN_DIR/runtime/$HOSTNAME"
LOG_FILE="$RUNTIME_DIR/hourly_scan_sync.log"

mkdir -p "$RUNTIME_DIR"
exec >>"$LOG_FILE" 2>&1

echo --------------------------------------------------------
echo STARTED SCAN: $(date)

cd "$SCAN_DIR"
./scan.sh

echo COMPLETED SCAN: $(date)
echo --------------------------------------------------------
