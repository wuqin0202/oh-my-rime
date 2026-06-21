"""Platform helpers for the Rime UserDB sync tool.

This module intentionally stays standard-library-only and focuses on
cross-platform path resolution plus operator override handling.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform as host_platform
from typing import Mapping, Optional


ANDROID_USER_DIR = Path(
    "/storage/emulated/0/Android/data/org.fcitx.fcitx5.android/files/data/rime"
)


@dataclass(frozen=True)
class PlatformSpec:
    """Resolved platform metadata used by the sync engine."""

    name: str
    user_dir: Path
    sync_dir: Path


def detect_platform(
    *,
    system: Optional[str] = None,
    environment: Optional[Mapping[str, str]] = None,
) -> str:
    """Return the canonical tool platform name.

    Canonical values:
    - macos
    - windows
    - linux
    - android
    """

    env = environment or os.environ
    raw_system = (system or host_platform.system()).strip().lower()

    if raw_system == "darwin":
        return "macos"
    if raw_system == "windows":
        return "windows"
    if raw_system == "linux":
        if env.get("ANDROID_ROOT") or env.get("ANDROID_STORAGE"):
            return "android"
        return "linux"
    raise ValueError(f"Unsupported platform: {system or host_platform.system()!r}")


def default_rime_user_dir(
    platform_name: str,
    *,
    environment: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Resolve the documented default Rime user directory for a platform."""

    env = environment or os.environ
    base_home = Path(home) if home is not None else Path.home()

    if platform_name == "macos":
        return base_home / "Library" / "Rime"
    if platform_name == "windows":
        appdata = env.get("APPDATA")
        if appdata:
            return Path(appdata) / "Rime"
        return base_home / "AppData" / "Roaming" / "Rime"
    if platform_name == "linux":
        return base_home / ".local" / "share" / "fcitx5" / "rime"
    if platform_name == "android":
        return ANDROID_USER_DIR
    raise ValueError(f"Unsupported platform: {platform_name!r}")


def default_sync_dir(user_dir: Path) -> Path:
    """Return the required local .sync workspace path."""

    return Path(user_dir) / ".sync"


def resolve_rime_user_dir(
    *,
    override: Optional[str] = None,
    platform_name: Optional[str] = None,
    environment: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return the effective Rime user directory with override precedence."""

    if override:
        return expand_user_path(override, home=home)

    resolved_platform = platform_name or detect_platform(
        environment=environment,
    )
    return default_rime_user_dir(
        resolved_platform,
        environment=environment,
        home=home,
    )


def resolve_platform_spec(
    *,
    user_dir_override: Optional[str] = None,
    platform_name: Optional[str] = None,
    environment: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> PlatformSpec:
    """Resolve the effective platform plus Rime and .sync directories."""

    resolved_platform = platform_name or detect_platform(
        environment=environment,
    )
    user_dir = resolve_rime_user_dir(
        override=user_dir_override,
        platform_name=resolved_platform,
        environment=environment,
        home=home,
    )
    return PlatformSpec(
        name=resolved_platform,
        user_dir=user_dir,
        sync_dir=default_sync_dir(user_dir),
    )


def expand_user_path(path_value: str, *, home: Optional[Path] = None) -> Path:
    """Expand a path with environment variables and ~ support."""

    expanded = os.path.expandvars(path_value)
    if expanded.startswith("~"):
        base_home = str(Path(home) if home is not None else Path.home())
        expanded = expanded.replace("~", base_home, 1)
    return Path(expanded)
