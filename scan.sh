#!/usr/bin/env bash
set -euo pipefail

NETWORK_PREFIX="192.168.1"
IFACE="eth0"
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_JSON="${BASE_DIR}/devices.json"
OUT_MD="${BASE_DIR}/devices.md"
HISTORY_JSON="${BASE_DIR}/.scan_history.json"
VERSION="v00.00.00"

# 1) Ping sweep to populate ARP/neigh cache
seq 1 254 | xargs -I{} -P 64 sh -c "ping -c 1 -W 1 ${NETWORK_PREFIX}.{} >/dev/null 2>&1 || true"

# 2) Build enriched JSON + Markdown
BASE_DIR="$BASE_DIR" IFACE="$IFACE" NETWORK_PREFIX="$NETWORK_PREFIX" OUT_JSON="$OUT_JSON" OUT_MD="$OUT_MD" HISTORY_JSON="$HISTORY_JSON" VERSION="$VERSION" python3 - <<'PY'
import os
import json
import socket
import datetime
import subprocess
from pathlib import Path

base_dir = Path(os.environ["BASE_DIR"])
iface = os.environ["IFACE"]
network_prefix = os.environ["NETWORK_PREFIX"]
out_json = Path(os.environ["OUT_JSON"])
out_md = Path(os.environ["OUT_MD"])
history_json = Path(os.environ["HISTORY_JSON"])
version = os.environ["VERSION"]

now = datetime.datetime.now().astimezone().isoformat()


def load_history(path: Path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data.get("devices", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_history(path: Path, devices_map):
    payload = {
        "version": version,
        "updated_at": now,
        "devices": devices_map,
    }
    path.write_text(json.dumps(payload, indent=2))


def load_oui_map():
    candidates = [
        Path("/usr/share/ieee-data/oui.txt"),
        Path("/usr/share/misc/oui.txt"),
    ]
    oui = {}
    for p in candidates:
        if not p.exists():
            continue
        try:
            for line in p.read_text(errors="ignore").splitlines():
                if "(base 16)" in line:
                    parts = line.split("(base 16)")
                    prefix = parts[0].strip().replace("-", "").replace(":", "").upper()
                    vendor = parts[1].strip()
                    if len(prefix) >= 6 and vendor:
                        oui[prefix[:6]] = vendor
            if oui:
                return oui
        except Exception:
            continue
    return oui


def normalize_mac(mac: str):
    return mac.replace(":", "").replace("-", "").upper()


def vendor_for_mac(mac: str, oui_map):
    if not mac:
        return None
    nm = normalize_mac(mac)
    if len(nm) < 6:
        return None
    return oui_map.get(nm[:6])


def resolve_hostname(ip: str):
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name
    except Exception:
        return None

raw = subprocess.check_output(["ip", "neigh", "show", "dev", iface], text=True)
history = load_history(history_json)
oui_map = load_oui_map()

seen_devices = []
updated_history = dict(history)

for line in raw.splitlines():
    line = line.strip()
    if not line:
        continue
    first = line.split()[0]
    if ":" in first:
        continue  # skip IPv6

    parts = line.split()
    ip = parts[0]
    state = parts[-1]
    mac = None
    if "lladdr" in parts:
        mac = parts[parts.index("lladdr") + 1].lower()

    if state in ("FAILED", "INCOMPLETE"):
        continue

    hostname = resolve_hostname(ip)
    manufacturer = vendor_for_mac(mac, oui_map)

    prev = history.get(ip, {})
    first_seen = prev.get("first_seen", now)
    last_seen = now

    device = {
        "ip": ip,
        "mac": mac,
        "hostname": hostname,
        "manufacturer": manufacturer,
        "state": state,
        "first_seen": first_seen,
        "last_seen": last_seen,
    }
    seen_devices.append(device)
    updated_history[ip] = {
        "ip": ip,
        "mac": mac,
        "hostname": hostname,
        "manufacturer": manufacturer,
        "first_seen": first_seen,
        "last_seen": last_seen,
    }

seen_devices.sort(key=lambda d: tuple(map(int, d["ip"].split("."))))

payload = {
    "version": version,
    "network": f"{network_prefix}.0/24",
    "scan_method": "ping sweep + arp/neigh table + reverse DNS + OUI lookup",
    "scanned_at": now,
    "count": len(seen_devices),
    "devices": seen_devices,
}
out_json.write_text(json.dumps(payload, indent=2))
save_history(history_json, updated_history)

# Markdown render
lines = [
    f"# Network Scan {version}",
    "",
    f"- **Network:** `{payload['network']}`",
    f"- **Scanned at:** `{payload['scanned_at']}`",
    f"- **Count:** `{payload['count']}`",
    f"- **Method:** {payload['scan_method']}",
    "",
    "| IP | MAC | Hostname | Manufacturer | State | First Seen | Last Seen |",
    "|---|---|---|---|---|---|---|",
]
for d in seen_devices:
    lines.append(
        f"| {d.get('ip') or ''} | {d.get('mac') or ''} | {d.get('hostname') or ''} | {d.get('manufacturer') or ''} | {d.get('state') or ''} | {d.get('first_seen') or ''} | {d.get('last_seen') or ''} |"
    )
out_md.write_text("\n".join(lines) + "\n")

print(str(out_json))
print(str(out_md))
print(payload["count"])
PY

echo "Wrote ${OUT_JSON}"
echo "Wrote ${OUT_MD}"