# Home Network Scan System

This project scans the home LAN, enriches devices with metadata, preserves history, exports into Obsidian, and syncs into Uptime Kuma.

## Project Layout

- `scan.py` — main pipeline (config load, ping sweep, collect, enrich, export, Kuma import)
- `scan.sh` — thin wrapper that loads `env.sh` and runs `uv run scan.py`
- `hourly_scan_sync.sh` — cron-safe wrapper, logs to host runtime folder, syncs `devices.json` to vault export
- `config.json` — all non-secret runtime config
- `env.sh` — local secrets (git-ignored), e.g. Kuma credentials
- `logs/<HOSTNAME>/` — runtime outputs for each host
- `SCAN_FUNCTIONS.md` — function-by-function reference for `scan.py`
- `AGENTS.md` — project operational context and current state
- `skill/` — copied skill source used in this workspace
- `cron/` — cron entry files for deployment

## End-to-End Flow

1. `scan.sh` optionally sources `env.sh`.
2. `scan.py` loads `config.json`.
3. `scan.py` resolves runtime output paths to `logs/<HOSTNAME>/...`.
4. Ping sweep runs over configured range.
5. Neighbor table (`ip neigh`) is parsed.
6. Each device is enriched with:
   - reverse DNS hostname (if available)
   - fallback name from `additional_devices`
   - OUI manufacturer lookup
   - semantic tags for downstream use
7. Outputs are written:
   - `logs/<HOSTNAME>/devices.json`
   - `logs/<HOSTNAME>/devices.md`
   - `logs/<HOSTNAME>/.scan_history.json`
8. Obsidian exports are written:
   - `systems/homenetwork/devices/*.md`
   - `systems/homenetwork/reports/*.base`
   - `systems/homenetwork/reports/diffs/*`
   - `systems/homenetwork/reports/latest-diff.md`
   - `systems/homenetwork/devices-overview.md`
9. Uptime Kuma import runs:
   - adds missing IPs as ping monitors
   - skips existing hosts
10. `hourly_scan_sync.sh` copies runtime `devices.json` to:
    - `.../TamClawVault/systems/homenetwork/device-exports/devices.json`

## Configuration

### `config.json`
Key sections:
- scan controls: `network_prefix`, `interface`, `scan_range_start/end`, ping settings
- runtime: `runtime_root`, output/history filenames
- vault export: `vault_path`, `systems_folder`
- uptime kuma defaults: under `uptime_kuma`
- additional static names: `additional_devices`

### `env.sh` (secrets)
Expected variables:
- `KUMA_URL`
- `KUMA_USERNAME`
- `KUMA_PASSWORD`

`scan.py` reads env vars first, then falls back to config for Kuma settings.

## Runtime Outputs

Per host, under `logs/<HOSTNAME>/`:
- `devices.json` — canonical machine-readable scan snapshot
- `devices.md` — human-readable table
- `.scan_history.json` — persistent first/last-seen history
- `hourly_scan_sync.log` — cron runtime log (written by `hourly_scan_sync.sh`)

## Cron

Cron definition files are stored in:
- `cron/hourly_scan_sync.cron`

Current schedule:
- `5 * * * * /home/tamclaw/.openclaw/workspace-darren/projects/homenetwork/scan/hourly_scan_sync.sh`

## Skill Information

This project now includes a copied skill source in:
- `skill/obsidian-task-manager.SKILL.md`

Source copied from workspace skills:
- `/home/tamclaw/.openclaw/workspace-darren/skills/obsidian-task-manager/SKILL.md`

Purpose of that skill: manage Obsidian project tasks and indexes with consistent metadata/badges.

## Running Manually

From project directory:

```bash
cd /home/tamclaw/.openclaw/workspace-darren/projects/homenetwork/scan
source ./env.sh   # optional but needed for Kuma auth
./scan.sh
```

Or direct:

```bash
uv run ./scan.py
```

## Notes

- This system preserves historical devices and marks unseen ones offline in vault exports.
- Device note identity prefers MAC-based filenames for stability.
- Current implementation does not generate Uptime Kuma backup JSON files; it performs direct import into Kuma.
