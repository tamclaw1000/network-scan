#!/usr/bin/env bash
set -euo pipefail

SCAN_DIR="/home/tamclaw/.openclaw/workspace-darren/projects/homenetwork/scan"
VAULT_EXPORT_DIR="/home/tamclaw/.openclaw/workspace/TamClawVault/systems/homenetwork/device-exports"
HOSTNAME="$(hostname)"
RUNTIME_DIR="$SCAN_DIR/logs/$HOSTNAME"
LOG_FILE="$RUNTIME_DIR/hourly_scan_sync.log"

mkdir -p "$RUNTIME_DIR"
exec >>"$LOG_FILE" 2>&1

cd "$SCAN_DIR"
./scan.sh

mkdir -p "$VAULT_EXPORT_DIR"
cp -f "$RUNTIME_DIR/devices.json" "$VAULT_EXPORT_DIR/devices.json"
