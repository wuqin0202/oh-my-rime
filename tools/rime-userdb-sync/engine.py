from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from filtering import DEFAULT_INCLUDE_PATTERNS, collect_local_snapshots, is_allowed_snapshot

SUPPORTED_PLATFORMS = {"darwin", "windows", "linux", "android"}
INSTALLATION_FIELD_ORDER = [
    "distribution_code_name",
    "distribution_name",
    "distribution_version",
    "install_time",
    "installation_id",
    "rime_version",
    "sync_dir",
    "update_time",
]


class SyncToolError(RuntimeError):
    pass


@dataclass
class ToolConfig:
    remote_root: str | None = None
    device_id: str | None = None
    rime_user_dir: str | None = None
    local_sync_dir: str | None = None
    rime_sync_command: list[str] | None = None
    rclone_binary: str = "rclone"
    include_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_INCLUDE_PATTERNS))
    platform_override: str | None = None
    interval_minutes: int | None = None
    android_allow_push: bool = False


@dataclass
class RuntimeContext:
    platform_name: str
    remote_root: str | None
    rime_user_dir: Path
    local_sync_dir: Path
    installation_path: Path
    installation_id: str
    rime_sync_command: list[str] | None
    include_patterns: list[str]
    rclone_binary: str


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""


class SubprocessRunner:
    def run(self, args: Sequence[str]) -> CommandResult:
        completed = subprocess.run(list(args), check=False, capture_output=True, text=True)
        return CommandResult(list(args), completed.returncode, completed.stdout, completed.stderr)


class StructuredLogger:
    def __init__(self, installation_id: str, log_path: Path | None, dry_run: bool) -> None:
        self.installation_id = installation_id
        self.log_path = log_path
        self.dry_run = dry_run

    def emit(self, phase: str, action: str, result: str, **extra: Any) -> None:
        payload = {
            "timestamp": utc_now_iso(),
            "installation_id": self.installation_id,
            "phase": phase,
            "action": action,
            "result": result,
        }
        payload.update(extra)
        line = json.dumps(payload, ensure_ascii=False)
        print(line)
        if self.log_path is not None and not self.dry_run:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


class LocalLock:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self.hostname = socket.gethostname()
        self.pid = os.getpid()
        self.acquired = False

    def acquire(self, *, dry_run: bool, cleanup_stale: bool) -> None:
        if self.lock_path.exists():
            existing = read_json_file(self.lock_path)
            existing_host = str(existing.get("hostname", ""))
            existing_pid = int(existing.get("pid", -1))
            if existing_host == self.hostname and is_process_alive(existing_pid):
                raise SyncToolError(
                    f"live lock present at {self.lock_path} for pid {existing_pid} on {existing_host}"
                )
            if not cleanup_stale:
                raise SyncToolError(
                    f"stale lock present at {self.lock_path}; rerun with --cleanup-stale-lock to clear it"
                )
            if not dry_run:
                self.lock_path.unlink()
        if dry_run:
            self.acquired = True
            return
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.lock_path,
            json.dumps(
                {"pid": self.pid, "hostname": self.hostname, "acquired_at": utc_now_iso()},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        self.acquired = True

    def release(self, *, dry_run: bool) -> None:
        if not self.acquired or dry_run:
            return
        if self.lock_path.exists():
            self.lock_path.unlink()
        self.acquired = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def detect_platform(override: str | None = None) -> str:
    if override:
        normalized = override.lower()
        if normalized not in SUPPORTED_PLATFORMS:
            raise SyncToolError(f"unsupported platform override: {override}")
        return normalized
    if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
        return "android"
    if sys.platform.startswith("darwin"):
        return "darwin"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def default_rime_user_dir(platform_name: str) -> Path:
    if platform_name == "darwin":
        return Path("~/Library/Rime").expanduser()
    if platform_name == "windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise SyncToolError("APPDATA is required to resolve the Weasel user directory")
        return Path(appdata) / "Rime"
    if platform_name == "android":
        return Path("/storage/emulated/0/Android/data/org.fcitx.fcitx5.android/files/data/rime")
    return Path("~/.local/share/fcitx5/rime").expanduser()


def normalize_remote_root(remote_root: str) -> str:
    stripped = remote_root.strip().rstrip("/")
    if not stripped:
        raise SyncToolError("remote_root must not be empty")
    return stripped


def load_json_config(config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SyncToolError(f"config file must contain a JSON object: {config_path}")
    return data


def build_tool_config(config_data: dict[str, Any], cli_overrides: dict[str, Any]) -> ToolConfig:
    merged = dict(config_data)
    merged.update({key: value for key, value in cli_overrides.items() if value is not None})
    include_patterns = merged.get("include_patterns") or DEFAULT_INCLUDE_PATTERNS
    command_value = merged.get("rime_sync_command")
    if isinstance(command_value, str):
        command_value = shlex.split(command_value)
    elif isinstance(command_value, list):
        command_value = [str(part) for part in command_value]
    elif command_value is not None:
        raise SyncToolError("rime_sync_command must be a string or array of strings")
    interval = merged.get("interval_minutes")
    return ToolConfig(
        remote_root=merged.get("remote_root"),
        device_id=merged.get("device_id"),
        rime_user_dir=merged.get("rime_user_dir"),
        local_sync_dir=merged.get("local_sync_dir"),
        rime_sync_command=command_value,
        rclone_binary=str(merged.get("rclone_binary", "rclone")),
        include_patterns=[str(pattern) for pattern in include_patterns],
        platform_override=merged.get("platform_override"),
        interval_minutes=int(interval) if interval is not None else None,
        android_allow_push=bool(merged.get("android_allow_push", False)),
    )


def resolve_runtime_context(config: ToolConfig, *, require_remote_root: bool) -> RuntimeContext:
    platform_name = detect_platform(config.platform_override)
    rime_user_dir = Path(config.rime_user_dir).expanduser() if config.rime_user_dir else default_rime_user_dir(platform_name)
    local_sync_dir = Path(config.local_sync_dir).expanduser() if config.local_sync_dir else rime_user_dir / ".sync"
    installation_path = rime_user_dir / "installation.yaml"
    installation_state = read_installation_yaml(installation_path) if installation_path.exists() else {}
    installation_id = str(config.device_id or installation_state.get("installation_id") or "").strip()
    if not installation_id:
        raise SyncToolError(
            "missing installation_id; set device_id in config/flags or repair installation.yaml first"
        )
    remote_root = normalize_remote_root(config.remote_root) if require_remote_root and config.remote_root else config.remote_root
    return RuntimeContext(
        platform_name=platform_name,
        remote_root=remote_root,
        rime_user_dir=rime_user_dir,
        local_sync_dir=local_sync_dir,
        installation_path=installation_path,
        installation_id=installation_id,
        rime_sync_command=config.rime_sync_command,
        include_patterns=config.include_patterns or list(DEFAULT_INCLUDE_PATTERNS),
        rclone_binary=config.rclone_binary,
    )


def strip_yaml_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def read_installation_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = raw_line.split(":", 1)
            data[key.strip()] = strip_yaml_scalar(value.strip())
    return data


def render_installation_yaml(data: dict[str, str]) -> str:
    ordered_keys = [key for key in INSTALLATION_FIELD_ORDER if key in data]
    ordered_keys.extend(sorted(key for key in data if key not in ordered_keys))
    lines: list[str] = []
    for key in ordered_keys:
        value = str(data[key]).replace('"', '\\"')
        lines.append(f'{key}: "{value}"')
    return "\n".join(lines) + "\n"


def validate_installation_sync_dir(ctx: RuntimeContext) -> dict[str, str]:
    if not ctx.installation_path.exists():
        raise SyncToolError(
            f"installation.yaml missing at {ctx.installation_path}; run repair-installation first"
        )
    state = read_installation_yaml(ctx.installation_path)
    current_sync_dir = state.get("sync_dir")
    expected = str(ctx.local_sync_dir)
    if current_sync_dir != expected:
        raise SyncToolError(
            "installation.yaml sync_dir is incompatible with local .sync workspace; "
            f"expected {expected!r}, found {current_sync_dir!r}. Run repair-installation first"
        )
    return state


def generate_installation_id() -> str:
    hostname = socket.gethostname().strip() or "rime-device"
    filtered = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in hostname)
    collapsed = filtered.strip("-") or "rime-device"
    return collapsed[:64]


def read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SyncToolError(f"expected JSON object in {path}")
    return data


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def backup_installation_file(path: Path, *, dry_run: bool) -> Path | None:
    if not path.exists():
        return None
    backup_path = path.with_name(f"installation.yaml.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    if not dry_run:
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def repair_installation_file(config: ToolConfig, *, dry_run: bool) -> dict[str, Any]:
    ctx = resolve_runtime_context(config, require_remote_root=False)
    if not dry_run:
        ctx.rime_user_dir.mkdir(parents=True, exist_ok=True)
    existing = read_installation_yaml(ctx.installation_path) if ctx.installation_path.exists() else {}
    backup_path = backup_installation_file(ctx.installation_path, dry_run=dry_run)
    data = dict(existing)
    data["installation_id"] = str(config.device_id or existing.get("installation_id") or generate_installation_id()).strip()
    data["sync_dir"] = str(ctx.local_sync_dir)
    data["update_time"] = utc_now_iso()
    if not dry_run:
        atomic_write_text(ctx.installation_path, render_installation_yaml(data))
    return {
        "installation_path": str(ctx.installation_path),
        "backup_path": str(backup_path) if backup_path else None,
        "installation_id": data["installation_id"],
        "sync_dir": str(ctx.local_sync_dir),
        "created": not existing,
        "dry_run": dry_run,
    }


def ensure_workspace(ctx: RuntimeContext, *, dry_run: bool) -> Path | None:
    if dry_run:
        return None
    ctx.local_sync_dir.mkdir(parents=True, exist_ok=True)
    log_path = ctx.local_sync_dir / "logs" / "rime-userdb-sync.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return log_path


def join_remote(root: str, relative_path: str) -> str:
    return f"{root.rstrip('/')}/{relative_path.replace(os.sep, '/').lstrip('/')}"


def list_allowed_remote_files(runner: SubprocessRunner, ctx: RuntimeContext) -> list[str]:
    if ctx.remote_root is None:
        raise SyncToolError("remote_root is required")
    result = runner.run([ctx.rclone_binary, "lsf", ctx.remote_root, "--recursive", "--files-only"])
    if result.returncode != 0:
        raise SyncToolError(f"rclone listing failed: {result.stderr.strip() or result.stdout.strip()}")
    allowed: list[str] = []
    for line in result.stdout.splitlines():
        candidate = line.strip()
        if candidate and is_allowed_snapshot(candidate, ctx.include_patterns):
            allowed.append(candidate)
    return allowed


def pull_remote_snapshots(runner: SubprocessRunner, ctx: RuntimeContext, logger: StructuredLogger, *, dry_run: bool) -> list[str]:
    allowed = list_allowed_remote_files(runner, ctx)
    if not allowed:
        logger.emit("pull", "enumerate", "skip", reason="no_remote_snapshots")
        return []
    logger.emit("pull", "enumerate", "ok", files=len(allowed))
    for relative_path in allowed:
        destination = ctx.local_sync_dir / relative_path
        logger.emit("pull", "copy", "ok" if not dry_run else "skip", path=relative_path, dry_run=dry_run)
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = runner.run([ctx.rclone_binary, "copyto", join_remote(ctx.remote_root or "", relative_path), str(destination)])
        if result.returncode != 0:
            raise SyncToolError(f"rclone pull failed for {relative_path}: {result.stderr.strip() or result.stdout.strip()}")
    return allowed


def run_local_merge(runner: SubprocessRunner, ctx: RuntimeContext, logger: StructuredLogger, *, dry_run: bool) -> bool:
    if not ctx.rime_sync_command:
        if ctx.platform_name == "android":
            logger.emit("merge", "invoke", "skip", reason="android_manual_merge_required")
            return False
        raise SyncToolError("rime_sync_command is required for non-Android sync; set it via config or CLI")
    logger.emit("merge", "invoke", "ok" if not dry_run else "skip", dry_run=dry_run)
    if dry_run:
        return True
    result = runner.run(ctx.rime_sync_command)
    if result.returncode != 0:
        raise SyncToolError(f"local Rime sync command failed: {result.stderr.strip() or result.stdout.strip()}")
    return True


def push_current_device_snapshots(runner: SubprocessRunner, ctx: RuntimeContext, logger: StructuredLogger, *, dry_run: bool) -> list[str]:
    device_root = ctx.local_sync_dir / ctx.installation_id
    snapshots = collect_local_snapshots(device_root, ctx.include_patterns)
    if not snapshots:
        logger.emit("push", "enumerate", "skip", reason="no_local_snapshots", device_id=ctx.installation_id)
        return []
    pushed: list[str] = []
    for path in snapshots:
        relative_path = path.relative_to(device_root).as_posix()
        remote_path = f"{ctx.installation_id}/{relative_path}"
        logger.emit("push", "copy", "ok" if not dry_run else "skip", path=remote_path, dry_run=dry_run)
        if not dry_run:
            result = runner.run([ctx.rclone_binary, "copyto", str(path), join_remote(ctx.remote_root or "", remote_path)])
            if result.returncode != 0:
                raise SyncToolError(f"rclone push failed for {remote_path}: {result.stderr.strip() or result.stdout.strip()}")
        pushed.append(remote_path)
    return pushed


def sync_once(config: ToolConfig, *, dry_run: bool, cleanup_stale_lock: bool, runner: SubprocessRunner | None = None) -> dict[str, Any]:
    runner = runner or SubprocessRunner()
    ctx = resolve_runtime_context(config, require_remote_root=True)
    validate_installation_sync_dir(ctx)
    log_path = ensure_workspace(ctx, dry_run=dry_run)
    logger = StructuredLogger(ctx.installation_id, log_path, dry_run)
    lock = LocalLock(ctx.local_sync_dir / "locks" / "rime-userdb-sync.lock.json")
    logger.emit("validate", "workspace", "ok", platform=ctx.platform_name, dry_run=dry_run)
    lock.acquire(dry_run=dry_run, cleanup_stale=cleanup_stale_lock)
    logger.emit("lock", "acquire", "ok" if not dry_run else "skip", dry_run=dry_run)
    try:
        pulled = pull_remote_snapshots(runner, ctx, logger, dry_run=dry_run)
        merged = run_local_merge(runner, ctx, logger, dry_run=dry_run)
        pushed: list[str] = []
        if ctx.platform_name == "android" and not merged and not config.android_allow_push:
            logger.emit("push", "gate", "skip", reason="android_requires_manual_merge_then_explicit_push")
        else:
            if ctx.platform_name == "android" and not merged and config.android_allow_push:
                raise SyncToolError("android push requires a successful merge in the same invocation or explicit push command")
            pushed = push_current_device_snapshots(runner, ctx, logger, dry_run=dry_run)
        logger.emit("sync", "complete", "ok", pulled=len(pulled), pushed=len(pushed), dry_run=dry_run)
        return {
            "platform": ctx.platform_name,
            "installation_id": ctx.installation_id,
            "pulled": pulled,
            "pushed": pushed,
            "dry_run": dry_run,
        }
    finally:
        lock.release(dry_run=dry_run)
        logger.emit("lock", "release", "ok" if not dry_run else "skip", dry_run=dry_run)


def push_only(config: ToolConfig, *, dry_run: bool, cleanup_stale_lock: bool, runner: SubprocessRunner | None = None) -> dict[str, Any]:
    runner = runner or SubprocessRunner()
    ctx = resolve_runtime_context(config, require_remote_root=True)
    validate_installation_sync_dir(ctx)
    log_path = ensure_workspace(ctx, dry_run=dry_run)
    logger = StructuredLogger(ctx.installation_id, log_path, dry_run)
    lock = LocalLock(ctx.local_sync_dir / "locks" / "rime-userdb-sync.lock.json")
    lock.acquire(dry_run=dry_run, cleanup_stale=cleanup_stale_lock)
    logger.emit("lock", "acquire", "ok" if not dry_run else "skip", dry_run=dry_run)
    try:
        pushed = push_current_device_snapshots(runner, ctx, logger, dry_run=dry_run)
        logger.emit("push", "complete", "ok", pushed=len(pushed), dry_run=dry_run)
        return {
            "platform": ctx.platform_name,
            "installation_id": ctx.installation_id,
            "pushed": pushed,
            "dry_run": dry_run,
        }
    finally:
        lock.release(dry_run=dry_run)
        logger.emit("lock", "release", "ok" if not dry_run else "skip", dry_run=dry_run)
