#!/usr/bin/env python3
import datetime
import json
import socket
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

FAILED_STATES = {"FAILED", "INCOMPLETE"}


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat()


def get_env_config() -> dict:
    import os

    base_dir = Path(__file__).resolve().parent
    cfg = {
        "iface": os.environ["IFACE"],
        "network_prefix": os.environ["NETWORK_PREFIX"],
        "out_json": Path(os.environ["OUT_JSON"]),
        "out_md": Path(os.environ["OUT_MD"]),
        "history_json": Path(os.environ["HISTORY_JSON"]),
        "version": os.environ["VERSION"],
        "base_dir": base_dir,
    }
    cfg["vault"] = load_export_config(base_dir)
    return cfg


def load_export_config(base_dir: Path) -> dict:
    cfg_path = base_dir / "config.json"
    if not cfg_path.exists():
        return {}
    data = json.loads(cfg_path.read_text())
    vault_path = Path(data["vault_path"])
    systems_folder = data["systems_folder"]
    return {
        "config_path": cfg_path,
        "vault_path": vault_path,
        "systems_folder": systems_folder,
        "version": data.get("version"),
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
    payload = {"version": version, "updated_at": ts, "devices": devices_map}
    path.write_text(json.dumps(payload, indent=2))


def load_oui_map() -> dict:
    candidates = [Path("/usr/share/ieee-data/oui.txt"), Path("/usr/share/misc/oui.txt")]
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
        return None
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
        if not parsed or parsed["state"] in FAILED_STATES:
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


def slug_ip(ip: str) -> str:
    return ip.replace('.', '-')


def write_obsidian_exports(vault_cfg: dict, payload: dict) -> None:
    if not vault_cfg:
        return

    base = Path(vault_cfg["vault_path"]) / vault_cfg["systems_folder"]
    devices_dir = base / "devices"
    reports_dir = base / "reports"
    devices_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # overview markdown based on devices.json data
    overview = base / "devices-overview.md"
    write_markdown(overview, payload)

    # one file per system with front matter
    for d in payload["devices"]:
        p = devices_dir / f"{slug_ip(d['ip'])}.md"
        fm = [
            "---",
            f"ip: {d.get('ip')}",
            f"mac: {d.get('mac') or ''}",
            f"hostname: {d.get('hostname') or ''}",
            f"manufacturer: {d.get('manufacturer') or ''}",
            f"state: {d.get('state')}",
            f"first_seen: {d.get('first_seen')}",
            f"last_seen: {d.get('last_seen')}",
            "---",
            "",
            f"# Device {d.get('ip')}",
            "",
            "## Summary",
            f"- Hostname: `{d.get('hostname') or 'unknown'}`",
            f"- Manufacturer: `{d.get('manufacturer') or 'unknown'}`",
            f"- MAC: `{d.get('mac') or 'unknown'}`",
            f"- State: `{d.get('state')}`",
        ]
        p.write_text("\n".join(fm) + "\n")

    # base reports
    by_state = Counter(d.get("state") or "unknown" for d in payload["devices"])
    by_mfg = Counter(d.get("manufacturer") or "unknown" for d in payload["devices"])
    new_this_scan = [d for d in payload["devices"] if d.get("first_seen") == payload["scanned_at"]]

    (reports_dir / "by-state.md").write_text(
        "# Report: Devices by State\n\n" +
        "\n".join(f"- **{k}**: {v}" for k, v in sorted(by_state.items())) + "\n"
    )

    (reports_dir / "by-manufacturer.md").write_text(
        "# Report: Devices by Manufacturer\n\n" +
        "\n".join(f"- **{k}**: {v}" for k, v in by_mfg.most_common()) + "\n"
    )

    lines = [
        "# Report: New Devices This Scan",
        "",
        f"Scan timestamp: `{payload['scanned_at']}`",
        f"Count: **{len(new_this_scan)}**",
        "",
    ]
    for d in new_this_scan:
        lines.append(f"- `{d['ip']}` · {d.get('hostname') or 'unknown'} · {d.get('manufacturer') or 'unknown'}")
    (reports_dir / "new-this-scan.md").write_text("\n".join(lines) + "\n")



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
    write_obsidian_exports(cfg.get("vault", {}), payload)

    print(str(cfg["out_json"]))
    print(str(cfg["out_md"]))
    if cfg.get("vault"):
        base = Path(cfg["vault"]["vault_path"]) / cfg["vault"]["systems_folder"]
        print(str(base))
    print(payload["count"])


if __name__ == "__main__":
    main()
