"""installation.yaml helpers for the Rime UserDB sync tool.

The sync tool uses installation.yaml only as a Rime runtime state file. Normal
sync should validate it; explicit repair flows may rewrite it safely.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import socket
import tempfile
from typing import Dict, Mapping, Optional


REQUIRED_MINIMAL_FIELDS = ("installation_id", "sync_dir", "update_time")
OPTIONAL_PRESERVED_FIELDS = (
    "distribution_code_name",
    "distribution_name",
    "distribution_version",
    "install_time",
    "rime_version",
)
_PAIR_RE = re.compile(r"^([A-Za-z0-9_]+):(?:[ ]+(.*))?$")


@dataclass(frozen=True)
class InstallationRecord:
    installation_id: str
    sync_dir: str
    update_time: str
    extras: Dict[str, str] = field(default_factory=dict)

    def as_flat_mapping(self) -> Dict[str, str]:
        data: Dict[str, str] = {
            "installation_id": self.installation_id,
            "sync_dir": self.sync_dir,
            "update_time": self.update_time,
        }
        data.update(self.extras)
        return data


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    code: str
    message: str


def read_installation_yaml(path: Path) -> InstallationRecord:
    """Parse the flat installation.yaml structure used by Rime."""

    parsed = _parse_flat_yaml(Path(path).read_text(encoding="utf-8"))

    missing = [field for field in REQUIRED_MINIMAL_FIELDS if not parsed.get(field)]
    if missing:
        raise ValueError(
            "installation.yaml is missing required fields: " + ", ".join(missing)
        )

    extras = {
        key: value
        for key, value in parsed.items()
        if key not in REQUIRED_MINIMAL_FIELDS
    }
    return InstallationRecord(
        installation_id=parsed["installation_id"],
        sync_dir=parsed["sync_dir"],
        update_time=parsed["update_time"],
        extras=extras,
    )


def validate_installation_sync_dir(
    path: Path,
    *,
    expected_sync_dir: Path,
) -> ValidationResult:
    """Fail closed when installation.yaml is missing or points elsewhere."""

    file_path = Path(path)
    if not file_path.exists():
        return ValidationResult(
            ok=False,
            code="missing_installation_yaml",
            message=(
                f"{file_path} is missing. Run the explicit repair/setup command "
                "before sync."
            ),
        )

    record = read_installation_yaml(file_path)
    actual = _normalize_path(Path(record.sync_dir))
    expected = _normalize_path(expected_sync_dir)
    if actual != expected:
        return ValidationResult(
            ok=False,
            code="sync_dir_mismatch",
            message=(
                "installation.yaml sync_dir does not match the required local "
                f".sync path. expected={expected} actual={actual}. Use the "
                "explicit repair/setup flow before sync."
            ),
        )

    return ValidationResult(
        ok=True,
        code="ok",
        message="installation.yaml sync_dir matches the required local .sync path.",
    )


def repair_installation_yaml(
    path: Path,
    *,
    expected_sync_dir: Path,
    installation_id: Optional[str] = None,
    now: Optional[datetime] = None,
    preserved_fields: Optional[Mapping[str, str]] = None,
) -> tuple[Path, InstallationRecord]:
    """Rewrite installation.yaml atomically and return (backup_path, record)."""

    file_path = Path(path)
    backup_path = backup_installation_yaml(file_path)

    existing: Dict[str, str] = {}
    if file_path.exists():
        existing = read_installation_yaml(file_path).as_flat_mapping()

    effective_now = now or datetime.now(timezone.utc)
    resolved_installation_id = (
        installation_id
        or existing.get("installation_id")
        or generated_installation_id()
    )

    extras: Dict[str, str] = {}
    for key in OPTIONAL_PRESERVED_FIELDS:
        if key in existing:
            extras[key] = existing[key]
    if preserved_fields:
        extras.update({key: str(value) for key, value in preserved_fields.items()})

    record = InstallationRecord(
        installation_id=resolved_installation_id,
        sync_dir=str(expected_sync_dir),
        update_time=_format_timestamp(effective_now),
        extras=extras,
    )
    _atomic_write(file_path, _dump_flat_yaml(record.as_flat_mapping()))
    return backup_path, record


def restore_installation_backup(path: Path, backup_path: Path) -> None:
    """Restore a previously created backup file atomically."""

    source = Path(backup_path)
    target = Path(path)
    _atomic_write(target, source.read_text(encoding="utf-8"))


def backup_installation_yaml(path: Path, *, now: Optional[datetime] = None) -> Path:
    """Create a timestamped backup or an empty marker if the file is missing."""

    file_path = Path(path)
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    backup_path = file_path.with_suffix(file_path.suffix + f".bak.{timestamp}")

    if file_path.exists():
        backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        backup_path.write_text("", encoding="utf-8")
    return backup_path


def generated_installation_id(*, hostname: Optional[str] = None) -> str:
    """Return a stable fallback installation identifier for explicit repair."""

    return f"generated-{(hostname or socket.gethostname()).strip().lower()}"


def _parse_flat_yaml(text: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PAIR_RE.match(line)
        if not match:
            raise ValueError(f"Unsupported installation.yaml line: {raw_line!r}")
        key, value = match.groups()
        parsed[key] = _strip_quotes((value or "").strip())
    return parsed


def _dump_flat_yaml(values: Mapping[str, str]) -> str:
    ordered_keys = list(REQUIRED_MINIMAL_FIELDS)
    ordered_keys.extend(
        key for key in OPTIONAL_PRESERVED_FIELDS if key in values and key not in ordered_keys
    )
    ordered_keys.extend(
        key for key in values.keys() if key not in ordered_keys
    )
    lines = [f"{key}: {values[key]}" for key in ordered_keys if key in values]
    return "\n".join(lines) + "\n"


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _atomic_write(path: Path, content: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=file_path.parent,
        delete=False,
    ) as handle:
        handle.write(content)
        temp_name = handle.name
    os.replace(temp_name, file_path)


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_path(path: Path) -> str:
    return str(path.expanduser())
