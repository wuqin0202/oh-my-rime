from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from engine import (
    SyncToolError,
    build_tool_config,
    load_json_config,
    push_only,
    repair_installation_file,
    sync_once,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rime-userdb-sync",
        description="Cross-platform Rime userdb snapshot sync tool.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Pull, merge locally, then push only the current device snapshots.")
    add_common_arguments(sync_parser)
    sync_parser.add_argument("--dry-run", action="store_true", help="Report planned actions without mutating local or remote state.")
    sync_parser.add_argument("--cleanup-stale-lock", action="store_true", help="Allow explicit stale-lock cleanup.")

    push_parser = subparsers.add_parser("push", help="Push only the current device snapshots after a manual merge.")
    add_common_arguments(push_parser)
    push_parser.add_argument("--dry-run", action="store_true")
    push_parser.add_argument("--cleanup-stale-lock", action="store_true")

    repair_parser = subparsers.add_parser("repair-installation", help="Back up and rewrite installation.yaml to local .sync.")
    add_common_arguments(repair_parser)
    repair_parser.add_argument("--dry-run", action="store_true")

    return parser


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, help="Path to the JSON config file.")
    parser.add_argument("--remote-root", help="rclone remote root containing per-device subdirectories.")
    parser.add_argument("--device-id", help="Explicit installation_id override for this device.")
    parser.add_argument("--rime-user-dir", help="Explicit Rime user directory override.")
    parser.add_argument("--local-sync-dir", help="Explicit local .sync directory override.")
    parser.add_argument("--rime-sync-command", help="Explicit local Rime sync command.")
    parser.add_argument("--rclone-binary", help="rclone executable name or path.")
    parser.add_argument("--platform", dest="platform_override", help="Force platform detection to darwin/windows/linux.")


def collect_cli_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "remote_root": args.remote_root,
        "device_id": args.device_id,
        "rime_user_dir": args.rime_user_dir,
        "local_sync_dir": args.local_sync_dir,
        "rime_sync_command": args.rime_sync_command,
        "rclone_binary": args.rclone_binary,
        "platform_override": args.platform_override,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config_data = load_json_config(args.config)
        config = build_tool_config(config_data, collect_cli_overrides(args))
        if args.command == "sync":
            if not config.remote_root:
                raise SyncToolError("sync requires --remote-root or remote_root in config")
            result = sync_once(config, dry_run=args.dry_run, cleanup_stale_lock=args.cleanup_stale_lock)
        elif args.command == "push":
            if not config.remote_root:
                raise SyncToolError("push requires --remote-root or remote_root in config")
            result = push_only(config, dry_run=args.dry_run, cleanup_stale_lock=args.cleanup_stale_lock)
        elif args.command == "repair-installation":
            result = repair_installation_file(config, dry_run=args.dry_run)
        else:
            raise SyncToolError(f"unsupported command: {args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except SyncToolError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
