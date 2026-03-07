#!/usr/bin/env bash
set -euo pipefail

SCAN_DIR="/home/tamclaw/.openclaw/workspace-darren/projects/homenetwork/scan"
VAULT_EXPORT_DIR="/home/tamclaw/.openclaw/workspace/TamClawVault/systems/homenetwork/device-exports"

cd "$SCAN_DIR"
./scan.sh

mkdir -p "$VAULT_EXPORT_DIR"
cp -f "$SCAN_DIR/devices.json" "$VAULT_EXPORT_DIR/devices.json"
