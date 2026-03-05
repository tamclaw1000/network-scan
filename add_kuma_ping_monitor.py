#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "uptime-kuma-api>=1.2.1",
# ]
# ///

"""
Add exactly one Uptime Kuma PING monitor.
All monitor parameters are provided via command line arguments.
Authentication supports either username/password or a login token.

Examples:

# Token auth
uv run /home/tamclaw/.openclaw/workspace-darren/projects/homenetwork/scan/add_kuma_ping_monitor.py \
  --url http://127.0.0.1:3001 \
  --login-token 'TOKEN_FROM_PREVIOUS_LOGIN' \
  --name 'LAN Ping - pi.hole (192.168.1.11)' \
  --hostname 192.168.1.11 \
  --interval 60 \
  --maxretries 1 \
  --retry-interval 60 \
  --resend-interval 0 \
  --dry-run

# Username/password auth
uv run /home/tamclaw/.openclaw/workspace-darren/projects/homenetwork/scan/add_kuma_ping_monitor.py \
  --url http://127.0.0.1:3001 \
  --username admin \
  --password 'secret' \
  --name 'LAN Ping - pi.hole (192.168.1.11)' \
  --hostname 192.168.1.11 \
  --interval 60 \
  --maxretries 1 \
  --retry-interval 60 \
  --resend-interval 0
"""

import argparse
from uptime_kuma_api import UptimeKumaApi, MonitorType, UptimeKumaException


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="Uptime Kuma URL, e.g. http://127.0.0.1:3001")

    auth = p.add_mutually_exclusive_group(required=True)
    auth.add_argument("--login-token", help="Login token for api.login_by_token(token)")
    auth.add_argument("--username", help="Uptime Kuma username (requires --password)")
    p.add_argument("--password", help="Uptime Kuma password (required with --username)")

    p.add_argument("--name", required=True, help="Monitor friendly name")
    p.add_argument("--hostname", required=True, help="Target hostname/IP to ping")
    p.add_argument("--interval", type=int, required=True, help="Heartbeat interval seconds")
    p.add_argument("--maxretries", type=int, required=True, help="Max retries before DOWN")
    p.add_argument("--retry-interval", type=int, required=True, dest="retry_interval", help="Retry interval seconds")
    p.add_argument("--resend-interval", type=int, required=True, dest="resend_interval", help="Resend interval")
    p.add_argument("--group-id", type=int, help="Optional monitor group id (parent)")
    p.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Tag assignment. Use NAME or NAME=VALUE. Repeat for multiple tags.",
    )
    p.add_argument("--tag-color", default="#1976d2", help="Color used when auto-creating missing tags")
    p.add_argument("--dry-run", action="store_true", help="Print payload only")

    args = p.parse_args()

    if args.username and not args.password:
        p.error("--password is required when using --username")

    return args


def parse_tag_arg(tag_arg: str) -> tuple[str, str]:
    if "=" in tag_arg:
        name, value = tag_arg.split("=", 1)
        return name.strip(), value.strip()
    return tag_arg.strip(), ""


def main() -> None:
    args = parse_args()
    payload = {
        "type": MonitorType.PING,
        "name": args.name,
        "hostname": args.hostname,
        "interval": args.interval,
        "maxretries": args.maxretries,
        "retryInterval": args.retry_interval,
        "resendInterval": args.resend_interval,
    }
    if args.group_id is not None:
        payload["parent"] = args.group_id

    parsed_tags = [parse_tag_arg(t) for t in args.tag if t.strip()]

    if args.dry_run:
        print(f"DRY-RUN add monitor: {payload}")
        if parsed_tags:
            print(f"DRY-RUN tags: {parsed_tags}")
        return

    with UptimeKumaApi(args.url) as api:
        try:
            if args.login_token:
                api.login_by_token(args.login_token)
            else:
                api.login(args.username, args.password)
        except UptimeKumaException as e:
            if "Invalid token" in str(e):
                raise SystemExit(
                    "Invalid login token. This API expects a session/login token from api.login(...), not an Uptime Kuma API key. "
                    "Use --username/--password or generate a fresh login token first."
                )
            raise

        result = api.add_monitor(**payload)
        print(result)

        monitor_id = result.get("monitorId") or result.get("monitorID")
        if monitor_id and parsed_tags:
            existing_tags = {t.get("name"): t for t in api.get_tags()}
            for tag_name, tag_value in parsed_tags:
                if tag_name not in existing_tags:
                    created = api.add_tag(name=tag_name, color=args.tag_color)
                    tag_id = created.get("tag", {}).get("id") or created.get("tagID") or created.get("id")
                    if not tag_id:
                        refreshed = {t.get("name"): t for t in api.get_tags()}
                        tag_id = (refreshed.get(tag_name) or {}).get("id")
                else:
                    tag_id = existing_tags[tag_name].get("id")

                if tag_id:
                    api.add_monitor_tag(tag_id=int(tag_id), monitor_id=int(monitor_id), value=tag_value)
                    print(f"tagged monitor {monitor_id}: {tag_name}={tag_value}")
                else:
                    print(f"warning: could not resolve tag id for '{tag_name}'")


if __name__ == "__main__":
    main()
