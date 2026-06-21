from __future__ import annotations

from pathlib import Path
import unittest


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"

ALLOWED_SUFFIX = ".userdb.txt"
FORBIDDEN_SUFFIXES = (".yaml", ".custom.yaml", ".schema.yaml", ".dict.yaml", ".log")
FORBIDDEN_DIR_SUFFIX = ".userdb"


class FilteringContractTest(unittest.TestCase):
    def test_allowlisted_remote_fixture_contains_only_userdb_snapshots(self) -> None:
        allowlisted_files = sorted(
            path.relative_to(FIXTURE_ROOT / "remote_all_devices").as_posix()
            for path in (FIXTURE_ROOT / "remote_all_devices").rglob("*")
            if path.is_file()
        )
        self.assertEqual(
            allowlisted_files,
            [
                "linux-fcitx5/mint.userdb.txt",
                "mac-squirrel/mint.userdb.txt",
                "win-weasel/mint.userdb.txt",
            ],
        )
        self.assertTrue(all(path.endswith(ALLOWED_SUFFIX) for path in allowlisted_files))

    def test_polluted_remote_fixture_contains_explicitly_forbidden_inputs(self) -> None:
        polluted_root = FIXTURE_ROOT / "remote_polluted"
        self.assertTrue((polluted_root / "mac-squirrel" / "default.custom.yaml").is_file())
        self.assertTrue((polluted_root / "linux-fcitx5" / "rime.log").is_file())
        self.assertTrue((polluted_root / "linux-fcitx5" / "mint.userdb" / "LOCK").is_file())

    def test_forbidden_fixture_names_match_contract_categories(self) -> None:
        polluted_paths = [
            path.relative_to(FIXTURE_ROOT / "remote_polluted").as_posix()
            for path in (FIXTURE_ROOT / "remote_polluted").rglob("*")
            if path.is_file()
        ]
        self.assertIn("mac-squirrel/default.custom.yaml", polluted_paths)
        self.assertIn("linux-fcitx5/rime.log", polluted_paths)
        self.assertTrue(
            any(path.name.endswith(FORBIDDEN_DIR_SUFFIX) for path in (FIXTURE_ROOT / "remote_polluted").rglob("*"))
        )
        self.assertTrue(any(path.endswith(".custom.yaml") for path in polluted_paths))
        self.assertTrue(any(path.endswith(".log") for path in polluted_paths))
        self.assertTrue(any(suffix in FORBIDDEN_SUFFIXES for suffix in (".custom.yaml", ".log")))


if __name__ == "__main__":
    unittest.main()
