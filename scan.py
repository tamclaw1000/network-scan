#!/usr/bin/env python3
import datetime
import json
import socket
import subprocess
from pathlib import Path


FAILED_STATES = {"FAILED", "INCOMPLETE"}


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat()


def get_env_config() -> dict:
    import os

    return {
        "iface": os.environ["IFACE"],
        "network_prefix": os.environ["NETWORK_PREFIX"],
        "out_json": Path(os.environ["OUT_JSON"]),
        "out_md": Path(os.environ["OUT_MD"]),
        "history_json": Path(os.environ["HISTORY_JSON"]),
        "version": os.environ["VERSION"],
    }


def load_history(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data.get("devices", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_history(path: Path, version: str, ts: str, devices_map: dict) -> None:
    payload = {
        "version": version,
        "updated_at": ts,
        "devices": devices_map,
    }
    path.write_text(json.dumps(payload, indent=2))


def load_oui_map() -> dict:
    candidates = [
        Path("/usr/share/ieee-data/oui.txt"),
        Path("/usr/share/misc/oui.txt"),
    ]
    oui = {}

    for path in candidates:
        if not path.exists():
            continue
        try:
            for line in path.read_text(errors="ignore").splitlines():
                if "(base 16)" not in line:
                    continue
                prefix_part, vendor_part = line.split("(base 16)", 1)
                prefix = prefix_part.strip().replace("-", "").replace(":", "").upper()
                vendor = vendor_part.strip()
                if len(prefix) >= 6 and vendor:
                    oui[prefix[:6]] = vendor
            if oui:
                return oui
        except Exception:
            continue

    return oui


def normalize_mac(mac: str | None) -> str | None:
    if not mac:
        return None
    return mac.replace(":", "").replace("-", "").upper()


def vendor_for_mac(mac: str | None, oui_map: dict) -> str | None:
    normalized = normalize_mac(mac)
    if not normalized or len(normalized) < 6:
        return None
    return oui_map.get(normalized[:6])


def resolve_hostname(ip: str) -> str | None:
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name
    except Exception:
        return None


def parse_neighbor_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None

    first_token = line.split()[0]
    if ":" in first_token:
        return None  # ignore IPv6

    parts = line.split()
    ip = parts[0]
    state = parts[-1]

    mac = None
    if "lladdr" in parts:
        mac = parts[parts.index("lladdr") + 1].lower()

    return {"ip": ip, "mac": mac, "state": state}


def collect_devices(iface: str, history: dict, oui_map: dict, ts: str) -> tuple[list, dict]:
    raw = subprocess.check_output(["ip", "neigh", "show", "dev", iface], text=True)
    devices = []
    updated_history = dict(history)

    for line in raw.splitlines():
        parsed = parse_neighbor_line(line)
        if not parsed:
            continue

        if parsed["state"] in FAILED_STATES:
            continue

        ip = parsed["ip"]
        mac = parsed["mac"]
        hostname = resolve_hostname(ip)
        manufacturer = vendor_for_mac(mac, oui_map)

        prev = history.get(ip, {})
        first_seen = prev.get("first_seen", ts)

        device = {
            "ip": ip,
            "mac": mac,
            "hostname": hostname,
            "manufacturer": manufacturer,
            "state": parsed["state"],
            "first_seen": first_seen,
            "last_seen": ts,
        }
        devices.append(device)

        updated_history[ip] = {
            "ip": ip,
            "mac": mac,
            "hostname": hostname,
            "manufacturer": manufacturer,
            "first_seen": first_seen,
            "last_seen": ts,
        }

    devices.sort(key=lambda d: tuple(map(int, d["ip"].split("."))))
    return devices, updated_history


def build_payload(version: str, network_prefix: str, ts: str, devices: list) -> dict:
    return {
        "version": version,
        "network": f"{network_prefix}.0/24",
        "scan_method": "ping sweep + arp/neigh table + reverse DNS + OUI lookup",
        "scanned_at": ts,
        "count": len(devices),
        "devices": devices,
    }


def write_markdown(path: Path, payload: dict) -> None:
    rows = [
        f"# Network Scan {payload['version']}",
        "",
        f"- **Network:** `{payload['network']}`",
        f"- **Scanned at:** `{payload['scanned_at']}`",
        f"- **Count:** `{payload['count']}`",
        f"- **Method:** {payload['scan_method']}",
        "",
        "| IP | MAC | Hostname | Manufacturer | State | First Seen | Last Seen |",
        "|---|---|---|---|---|---|---|",
    ]

    for d in payload["devices"]:
        rows.append(
            f"| {d.get('ip') or ''} | {d.get('mac') or ''} | {d.get('hostname') or ''} | {d.get('manufacturer') or ''} | {d.get('state') or ''} | {d.get('first_seen') or ''} | {d.get('last_seen') or ''} |"
        )

    path.write_text("\n".join(rows) + "\n")


def main() -> None:
    cfg = get_env_config()
    ts = now_iso()

    history = load_history(cfg["history_json"])
    oui_map = load_oui_map()

    devices, updated_history = collect_devices(cfg["iface"], history, oui_map, ts)
    payload = build_payload(cfg["version"], cfg["network_prefix"], ts, devices)

    cfg["out_json"].write_text(json.dumps(payload, indent=2))
    save_history(cfg["history_json"], cfg["version"], ts, updated_history)
    write_markdown(cfg["out_md"], payload)

    print(str(cfg["out_json"]))
    print(str(cfg["out_md"]))
    print(payload["count"])


if __name__ == "__main__":
    main()
