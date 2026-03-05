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
    base_dir = Path(__file__).resolve().parent
    cfg_path = base_dir / "config.json"
    data = json.loads(cfg_path.read_text())

    cfg = {
        "iface": data["interface"],
        "network_prefix": data["network_prefix"],
        "out_json": base_dir / data["output_json"],
        "out_md": base_dir / data["output_markdown"],
        "history_json": base_dir / data["history_file"],
        "version": data["version"],
        "base_dir": base_dir,
    }
    cfg["vault"] = {
        "config_path": cfg_path,
        "vault_path": Path(data["vault_path"]),
        "systems_folder": data["systems_folder"],
        "version": data.get("version"),
    }
    return cfg


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


def slug_mac(mac: str | None) -> str | None:
    if not mac:
        return None
    return mac.replace(':', '-').lower()


def device_note_name(device: dict) -> str:
    mac_slug = slug_mac(device.get("mac"))
    if mac_slug:
        return mac_slug
    return f"ip-{slug_ip(device.get('ip') or 'unknown')}"


def write_overview_markdown_with_links(path: Path, payload: dict) -> None:
    rows = [
        f"# Network Scan {payload['version']}",
        "",
        f"- **Network:** `{payload['network']}`",
        f"- **Scanned at:** `{payload['scanned_at']}`",
        f"- **Count:** `{payload['count']}`",
        f"- **Method:** {payload['scan_method']}",
        "",
        "| Device | IP | MAC | Hostname | Manufacturer | State | First Seen | Last Seen |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in payload["devices"]:
        note = f"devices/{device_note_name(d)}"
        rows.append(
            f"| [[{note}]] | {d.get('ip') or ''} | {d.get('mac') or ''} | {d.get('hostname') or ''} | {d.get('manufacturer') or ''} | {d.get('state') or ''} | {d.get('first_seen') or ''} | {d.get('last_seen') or ''} |"
        )
    path.write_text("\n".join(rows) + "\n")


def build_scan_diff(previous_payload: dict | None, current_payload: dict) -> dict:
    prev_devices = {d.get('ip'): d for d in (previous_payload or {}).get('devices', []) if d.get('ip')}
    curr_devices = {d.get('ip'): d for d in current_payload.get('devices', []) if d.get('ip')}

    prev_ips = set(prev_devices)
    curr_ips = set(curr_devices)

    new_ips = sorted(curr_ips - prev_ips, key=lambda x: tuple(map(int, x.split('.'))))
    lost_ips = sorted(prev_ips - curr_ips, key=lambda x: tuple(map(int, x.split('.'))))

    changed = []
    for ip in sorted(prev_ips & curr_ips, key=lambda x: tuple(map(int, x.split('.')))):
        before = prev_devices[ip]
        after = curr_devices[ip]
        fields = []
        for key in ("hostname", "manufacturer", "mac", "state"):
            if (before.get(key) or "") != (after.get(key) or ""):
                fields.append({"field": key, "before": before.get(key), "after": after.get(key)})
        if fields:
            changed.append({"ip": ip, "fields": fields})

    return {
        "previous_scanned_at": (previous_payload or {}).get("scanned_at"),
        "current_scanned_at": current_payload.get("scanned_at"),
        "previous_count": len(prev_ips),
        "current_count": len(curr_ips),
        "new": [{"ip": ip, **curr_devices[ip]} for ip in new_ips],
        "lost": [{"ip": ip, **prev_devices[ip]} for ip in lost_ips],
        "changed": changed,
    }


def write_uptime_kuma_backup(base_dir: Path, payload: dict) -> Path:
    """Generate a Uptime Kuma backup JSON from current scan payload.

    Output intentionally contains only flat ping monitors (no groups/tags)
    to keep imports and diffs simple.
    """
    stamp = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
    out_path = base_dir / f"Uptime_Kuma_Backup_from_scan_{stamp}.json"

    monitors = []
    next_id = 1
    for d in payload.get("devices", []):
        ip = d.get("ip")
        if not ip:
            continue
        name = (d.get("hostname") or "").strip() or ip
        monitors.append(
            {
                "id": next_id,
                "name": name,
                "description": None,
                "pathName": name,
                "parent": None,
                "childrenIDs": [],
                "url": None,
                "method": "GET",
                "hostname": ip,
                "port": None,
                "maxretries": 3,
                "weight": 2000,
                "active": True,
                "forceInactive": False,
                "type": "ping",
                "timeout": 48,
                "interval": 60,
                "retryInterval": 60,
                "resendInterval": 0,
                "keyword": None,
                "invertKeyword": False,
                "expiryNotification": True,
                "ignoreTls": False,
                "upsideDown": False,
                "packetSize": 56,
                "maxredirects": 10,
                "accepted_statuscodes": ["200-299"],
                "dns_resolve_type": None,
                "dns_resolve_server": None,
                "dns_last_result": None,
                "docker_container": None,
                "docker_host": None,
                "proxyId": None,
                "notificationIDList": {},
                "tags": [],
                "maintenance": False,
                "mqttTopic": None,
                "mqttSuccessMessage": None,
                "databaseQuery": None,
                "authMethod": None,
                "grpcUrl": None,
                "grpcProtobuf": None,
                "grpcMethod": None,
                "grpcServiceName": None,
                "grpcEnableTls": False,
                "radiusCalledStationId": None,
                "radiusCallingStationId": None,
                "game": None,
                "gamedigGivenPortOnly": True,
                "httpBodyEncoding": None,
                "jsonPath": None,
                "expectedValue": None,
                "kafkaProducerTopic": None,
                "kafkaProducerBrokers": None,
                "kafkaProducerSsl": False,
                "kafkaProducerAllowAutoTopicCreation": False,
                "kafkaProducerMessage": None,
                "screenshot": None,
                "headers": None,
                "body": None,
                "grpcBody": None,
                "grpcMetadata": None,
                "basic_auth_user": None,
                "basic_auth_pass": None,
                "oauth_client_id": None,
                "oauth_client_secret": None,
                "oauth_token_url": None,
                "oauth_scopes": None,
                "oauth_auth_method": None,
                "pushToken": None,
                "databaseConnectionString": None,
                "radiusUsername": None,
                "radiusPassword": None,
                "radiusSecret": None,
                "mqttUsername": None,
                "mqttPassword": None,
                "authWorkstation": None,
                "authDomain": None,
                "tlsCa": None,
                "tlsCert": None,
                "tlsKey": None,
                "kafkaProducerSaslOptions": None,
                "includeSensitiveData": True,
            }
        )
        next_id += 1

    backup = {
        "version": "1.23.13",
        "notificationList": [],
        "monitorList": monitors,
    }

    out_path.write_text(json.dumps(backup, indent=2))
    (base_dir / "Uptime_Kuma_Backup_from_scan_latest.json").write_text(json.dumps(backup, indent=2))
    return out_path


def write_obsidian_exports(vault_cfg: dict, payload: dict, previous_payload: dict | None = None) -> None:
    if not vault_cfg:
        return

    base = Path(vault_cfg["vault_path"]) / vault_cfg["systems_folder"]
    devices_dir = base / "devices"
    reports_dir = base / "reports"
    diffs_dir = reports_dir / "diffs"
    devices_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    diffs_dir.mkdir(parents=True, exist_ok=True)

    # overview markdown with links to per-device notes
    overview = base / "devices-overview.md"
    write_overview_markdown_with_links(overview, payload)

    # replace generated device note set each run to avoid stale entries
    for existing in devices_dir.glob("*.md"):
        existing.unlink()

    # one file per system with front matter
    for d in payload["devices"]:
        p = devices_dir / f"{device_note_name(d)}.md"
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

    # Obsidian Bases reports (using device front matter)
    devices_folder = f"{vault_cfg['systems_folder']}/devices"

    (reports_dir / "all-devices.base").write_text(
        "filters:\n"
        "  and:\n"
        f"    - file.inFolder(\"{devices_folder}\")\n"
        "    - file.ext == \"md\"\n"
        "views:\n"
        "  - type: table\n"
        "    name: All Devices\n"
        "    order:\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - ip\n"
        "    properties:\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - ip\n"
        "      - mac\n"
        "      - state\n"
        "      - first_seen\n"
        "      - last_seen\n"
        "      - file.path\n"
    )

    (reports_dir / "by-state.base").write_text(
        "filters:\n"
        "  and:\n"
        f"    - file.inFolder(\"{devices_folder}\")\n"
        "    - file.ext == \"md\"\n"
        "views:\n"
        "  - type: table\n"
        "    name: Devices by State\n"
        "    groupBy:\n"
        "      property: state\n"
        "      direction: ASC\n"
        "    order:\n"
        "      - state\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - ip\n"
        "    properties:\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - ip\n"
        "      - mac\n"
        "      - state\n"
        "      - last_seen\n"
        "      - file.path\n"
    )

    (reports_dir / "by-manufacturer.base").write_text(
        "filters:\n"
        "  and:\n"
        f"    - file.inFolder(\"{devices_folder}\")\n"
        "    - file.ext == \"md\"\n"
        "views:\n"
        "  - type: table\n"
        "    name: Devices by Manufacturer\n"
        "    groupBy:\n"
        "      property: manufacturer\n"
        "      direction: ASC\n"
        "    order:\n"
        "      - manufacturer\n"
        "      - hostname\n"
        "      - ip\n"
        "    properties:\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - ip\n"
        "      - mac\n"
        "      - state\n"
        "      - last_seen\n"
        "      - file.path\n"
    )

    (reports_dir / "new-this-scan.base").write_text(
        "filters:\n"
        "  and:\n"
        f"    - file.inFolder(\"{devices_folder}\")\n"
        "    - file.ext == \"md\"\n"
        f"    - first_seen == \"{payload['scanned_at']}\"\n"
        "views:\n"
        "  - type: table\n"
        "    name: New This Scan\n"
        "    order:\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - ip\n"
        "    properties:\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - ip\n"
        "      - mac\n"
        "      - first_seen\n"
        "      - file.path\n"
    )

    (reports_dir / "by-first-seen.base").write_text(
        "filters:\n"
        "  and:\n"
        f"    - file.inFolder(\"{devices_folder}\")\n"
        "    - file.ext == \"md\"\n"
        "views:\n"
        "  - type: table\n"
        "    name: Devices by First Seen\n"
        "    groupBy:\n"
        "      property: first_seen\n"
        "      direction: ASC\n"
        "    order:\n"
        "      - first_seen\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - ip\n"
        "    properties:\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - first_seen\n"
        "      - ip\n"
        "      - mac\n"
        "      - state\n"
        "      - file.path\n"
    )

    (reports_dir / "by-last-seen.base").write_text(
        "filters:\n"
        "  and:\n"
        f"    - file.inFolder(\"{devices_folder}\")\n"
        "    - file.ext == \"md\"\n"
        "views:\n"
        "  - type: table\n"
        "    name: Devices by Last Seen\n"
        "    groupBy:\n"
        "      property: last_seen\n"
        "      direction: DESC\n"
        "    order:\n"
        "      - last_seen\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - ip\n"
        "    properties:\n"
        "      - hostname\n"
        "      - manufacturer\n"
        "      - last_seen\n"
        "      - ip\n"
        "      - mac\n"
        "      - state\n"
        "      - file.path\n"
    )

    # per-run diff log
    diff = build_scan_diff(previous_payload, payload)
    stamp = payload["scanned_at"].replace(":", "").replace("+", "_plus_")
    diff_path = diffs_dir / f"scan-diff-{stamp}.md"

    lines = [
        "# Scan Diff",
        "",
        f"- Previous scan: `{diff.get('previous_scanned_at')}`",
        f"- Current scan: `{diff.get('current_scanned_at')}`",
        f"- Device count: **{diff.get('previous_count')} -> {diff.get('current_count')}**",
        "",
        f"## New Devices ({len(diff['new'])})",
    ]
    for d in diff["new"]:
        lines.append(f"- `{d.get('ip')}` · {d.get('hostname') or 'unknown'} · {d.get('manufacturer') or 'unknown'}")

    lines.append("")
    lines.append(f"## Lost Devices ({len(diff['lost'])})")
    for d in diff["lost"]:
        lines.append(f"- `{d.get('ip')}` · {d.get('hostname') or 'unknown'} · {d.get('manufacturer') or 'unknown'}")

    lines.append("")
    lines.append(f"## Changed Devices ({len(diff['changed'])})")
    for c in diff["changed"]:
        lines.append(f"- `{c['ip']}`")
        for f in c["fields"]:
            lines.append(f"  - {f['field']}: `{f.get('before')}` -> `{f.get('after')}`")

    diff_path.write_text("\n".join(lines) + "\n")
    (reports_dir / "latest-diff.md").write_text("\n".join(lines) + "\n")



def main() -> None:
    cfg = get_env_config()
    ts = now_iso()

    previous_payload = None
    if cfg["out_json"].exists():
        try:
            previous_payload = json.loads(cfg["out_json"].read_text())
        except Exception:
            previous_payload = None

    history = load_history(cfg["history_json"])
    oui_map = load_oui_map()

    devices, updated_history = collect_devices(cfg["iface"], history, oui_map, ts)
    payload = build_payload(cfg["version"], cfg["network_prefix"], ts, devices)

    cfg["out_json"].write_text(json.dumps(payload, indent=2))
    save_history(cfg["history_json"], cfg["version"], ts, updated_history)
    write_markdown(cfg["out_md"], payload)
    write_obsidian_exports(cfg.get("vault", {}), payload, previous_payload)
    kuma_backup_path = write_uptime_kuma_backup(cfg["base_dir"], payload)

    print(str(cfg["out_json"]))
    print(str(cfg["out_md"]))
    print(str(kuma_backup_path))
    if cfg.get("vault"):
        base = Path(cfg["vault"]["vault_path"]) / cfg["vault"]["systems_folder"]
        print(str(base))
    print(payload["count"])


if __name__ == "__main__":
    main()
