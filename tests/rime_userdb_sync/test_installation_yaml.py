from __future__ import annotations

from pathlib import Path
import unittest


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
REQUIRED_FIELDS = ("installation_id", "sync_dir", "update_time")


class InstallationYamlContractTest(unittest.TestCase):
    def test_local_fixture_points_to_local_sync_workspace(self) -> None:
        contents = (FIXTURE_ROOT / "local_rime_base" / "installation.yaml").read_text(encoding="utf-8")
        self.assertIn('sync_dir: "/Users/example/Library/Rime/.sync"', contents)

    def test_incompatible_fixture_preserves_cloud_backed_migration_edge(self) -> None:
        contents = (FIXTURE_ROOT / "incompatible_sync_dir" / "installation.yaml").read_text(encoding="utf-8")
        self.assertIn('sync_dir: "/Users/wuqin/Nutstore Files/.symlinks/坚果云/rime"', contents)

    def test_installation_yaml_fixtures_contain_required_fields(self) -> None:
        for relative in (
            "local_rime_base/installation.yaml",
            "incompatible_sync_dir/installation.yaml",
        ):
            contents = (FIXTURE_ROOT / relative).read_text(encoding="utf-8")
            for field in REQUIRED_FIELDS:
                self.assertIn(f"{field}:", contents, relative)

    def test_missing_installation_yaml_fixture_is_explicit(self) -> None:
        missing_root = FIXTURE_ROOT / "missing_installation_yaml"
        self.assertFalse((missing_root / "installation.yaml").exists())
        self.assertTrue((missing_root / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
