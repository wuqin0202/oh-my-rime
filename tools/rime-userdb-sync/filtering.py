from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable

DEFAULT_INCLUDE_PATTERNS = ["*.userdb.txt"]


def is_allowed_snapshot(relative_path: str, include_patterns: Iterable[str] | None = None) -> bool:
    patterns = list(include_patterns or DEFAULT_INCLUDE_PATTERNS)
    normalized = relative_path.replace("\\", "/").lstrip("/")
    if not normalized:
        return False
    parts = [part for part in normalized.split("/") if part]
    if any(part.endswith(".userdb") for part in parts[:-1]):
        return False
    filename = parts[-1]
    return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)


def collect_local_snapshots(device_root: Path, include_patterns: Iterable[str] | None = None) -> list[Path]:
    patterns = list(include_patterns or DEFAULT_INCLUDE_PATTERNS)
    if not device_root.exists():
        return []
    snapshots: list[Path] = []
    for path in sorted(device_root.rglob("*")):
        if path.is_dir():
            continue
        relative_path = path.relative_to(device_root).as_posix()
        if is_allowed_snapshot(relative_path, patterns):
            snapshots.append(path)
    return snapshots
