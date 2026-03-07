# AGENTS.md — homenetwork/scan Project Context

## Purpose
Scan the home network, preserve device history, and export device/report artifacts into the Obsidian vault.

## Project Location
`/home/tamclaw/.openclaw/workspace-darren/projects/homenetwork/scan`

## Primary Files
- `scan.py` — main scanner and export pipeline (now includes ping sweep)
- `scan.sh` — thin wrapper (loads `env.sh`, runs `uv run scan.py`)
- `config.json` — scanner configuration (includes `runtime_root`, `additional_devices`, Kuma defaults)
- `env.sh` — local secret env vars (`KUMA_URL`, `KUMA_USERNAME`, `KUMA_PASSWORD`), git-ignored
- `hourly_scan_sync.sh` — scheduled sync runner
- `SCAN_FUNCTIONS.md` — function-by-function documentation for `scan.py`

## Vault Export Targets
Base path:
`/home/tamclaw/.openclaw/workspace/TamClawVault/systems/homenetwork`

Outputs:
- `devices/*.md` — per-device notes (MAC-based filenames)
- `reports/*.base` — Obsidian Bases report definitions
- `reports/diffs/*` and `reports/latest-diff.md` — scan deltas
- `devices-overview.md` — consolidated active + historical summary

## Known Behaviors
- Devices missing from latest scan are preserved as historical/offline (not deleted).
- Reports include both device roots:
  - `systems/homenetwork/devices`
  - `21 - Claw/systems/homenetwork/devices`
- Sort preferences implemented:
  - `first_seen`: DESC
  - `last_seen`: ASC

## Runtime Layout (Current)
- Host-scoped runtime directory:
  - `logs/<HOSTNAME>/`
- Current host path:
  - `logs/tamclaw.tam.net/`
- Runtime artifacts written there:
  - `devices.json`
  - `devices.md`
  - `.scan_history.json`
  - `hourly_scan_sync.log`

## Automation
- Cron (confirmed):
  - `5 * * * * .../projects/homenetwork/scan/hourly_scan_sync.sh`
- Hourly sync copies runtime `devices.json` to vault export:
  - `.../systems/homenetwork/device-exports/devices.json`

## Current Execution State (as of latest run)
- Script run verified successfully in this session.
- Scan count from latest run: 88 devices.
- Uptime Kuma import path active:
  - latest run result: `added=0 skipped=88 failed=0`
- `scan.py` function-level docstrings are now present for all functions.
- Reference function docs file: `SCAN_FUNCTIONS.md`

## Known Gap
- `uptime_kuma_tags` can be empty for offline/historical device notes because tag data is not always persisted for historical-only entries in export path.

## Working Rules for Agents
- Do **not** delete historical records unless explicitly asked.
- Keep MAC-based note identity stable.
- Preserve dual-folder filter behavior in `.base` reports.
- Document schema/output changes here and in project notes.

## TODO
- [ ] Move the project into `~/projects`
- [ ] Rename project to `tamsidian-network-scan`
- [ ] Split code from run-time
- [ ] Migrate to `linuxpc03` and move from OpenClaw cronjobs to regular cronjobs; run under root

## Maintenance Notes (2026-03-06)
- `scan.py` now owns ping sweep execution and config parsing for sweep settings.
- `scan.sh` is a thin wrapper (loads `env.sh`, runs `uv run scan.py`).
- Function-level docstrings were added across `scan.py`.
- Detailed function reference: `SCAN_FUNCTIONS.md`.
