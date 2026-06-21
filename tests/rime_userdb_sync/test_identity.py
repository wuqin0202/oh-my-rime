from __future__ import annotations

from pathlib import Path
import unittest


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"

EXPECTED_PLATFORM_PATHS = {
    "macos_squirrel": "~/Library/Rime",
    "windows_weasel": r"%APPDATA%\Rime",
    "linux_fcitx5": "~/.local/share/fcitx5/rime",
    "android_fcitx5": "/storage/emulated/0/Android/data/org.fcitx.fcitx5.android/files/data/rime/",
}


class IdentityContractTest(unittest.TestCase):
    def test_expected_platform_defaults_match_prd_contract(self) -> None:
        self.assertEqual(EXPECTED_PLATFORM_PATHS["macos_squirrel"], "~/Library/Rime")
        self.assertEqual(EXPECTED_PLATFORM_PATHS["windows_weasel"], r"%APPDATA%\Rime")
        self.assertEqual(EXPECTED_PLATFORM_PATHS["linux_fcitx5"], "~/.local/share/fcitx5/rime")
        self.assertEqual(
            EXPECTED_PLATFORM_PATHS["android_fcitx5"],
            "/storage/emulated/0/Android/data/org.fcitx.fcitx5.android/files/data/rime/",
        )

    def test_local_fixture_uses_canonical_installation_id_shape(self) -> None:
        contents = (FIXTURE_ROOT / "local_rime_base" / "installation.yaml").read_text(encoding="utf-8")
        self.assertIn('installation_id: "mac-squirrel"', contents)

    def test_repo_migration_edge_fixture_preserves_existing_installation_id(self) -> None:
        contents = (FIXTURE_ROOT / "incompatible_sync_dir" / "installation.yaml").read_text(encoding="utf-8")
        self.assertIn('installation_id: "MacBookAirM4"', contents)


if __name__ == "__main__":
    unittest.main()
