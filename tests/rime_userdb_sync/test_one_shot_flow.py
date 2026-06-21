from __future__ import annotations

import json
from pathlib import Path
import unittest


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


class OneShotFlowContractTest(unittest.TestCase):
    def test_contract_fixture_enforces_pull_merge_push_order(self) -> None:
        contract = json.loads((FIXTURE_ROOT / "one_shot_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["phase_order"], ["validate", "pull", "merge", "push"])

    def test_contract_fixture_requires_upload_block_after_merge_failure(self) -> None:
        contract = json.loads((FIXTURE_ROOT / "one_shot_contract.json").read_text(encoding="utf-8"))
        self.assertFalse(contract["failure_expectations"]["merge_failure"]["push_allowed"])
        self.assertFalse(contract["failure_expectations"]["pull_failure"]["merge_allowed"])
        self.assertFalse(contract["failure_expectations"]["pull_failure"]["push_allowed"])

    def test_contract_fixture_covers_one_shot_manual_execution(self) -> None:
        contract = json.loads((FIXTURE_ROOT / "one_shot_contract.json").read_text(encoding="utf-8"))
        self.assertTrue(contract["manual_one_shot"]["supported"])
        self.assertTrue(contract["manual_one_shot"]["dry_run_supported"])
        self.assertEqual(contract["manual_one_shot"]["mode"], "explicit-user-invocation")


if __name__ == "__main__":
    unittest.main()
