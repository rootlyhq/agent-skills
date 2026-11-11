"""Strict-validation evidence is retained without rewriting a prior run."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import check_claude_package


class ClaudePackageCheckTests(unittest.TestCase):
    @staticmethod
    def payload(target, kind="plugin"):
        return {"success": True, "strict": True, "target": str(target),
                "manifest": {"file": str(target), "type": kind, "errors": [], "warnings": []},
                "contents": []}

    def test_all_command_outputs_and_failure_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "release-inventory.json").write_text("{}")
            responses = [subprocess.CompletedProcess([], code,
                         json.dumps(self.payload(root / ".claude-plugin" / (kind + ".json"), kind)),
                         "warning" if code else "")
                         for code, kind in ((0, "marketplace"), (1, "plugin"), (0, "marketplace"))]
            with patch.object(check_claude_package.subprocess, "check_output", return_value="test CLI"), \
                 patch.object(check_claude_package.subprocess, "run", side_effect=responses) as run:
                report = check_claude_package.check(root, root / "evidence")
            self.assertFalse(report["passed"])
            self.assertEqual(len(report["checks"]), 3)
            self.assertEqual(run.call_count, 3)
            self.assertEqual(len(report["validated_targets"]), 1)
            self.assertEqual((root / "evidence/plugin.stderr").read_text(), "warning")
            self.assertEqual(json.loads((root / "evidence/result.json").read_text()), report)
            with self.assertRaises(FileExistsError):
                check_claude_package.check(root, root / "evidence")

    def test_zero_exit_cannot_hide_invalid_json_or_reported_warnings(self):
        good = self.payload("/fixture/plugin.json")
        self.assertTrue(check_claude_package.validation_summary(json.dumps(good))["passed"])
        for stdout in ("not json", "null", "{}", '{"fixture":true}',
                       json.dumps(dict(good, success=False)), json.dumps(dict(good, strict=False)),
                       json.dumps(dict(good, contents=[{"warnings": ["nested warning"]}]))):
            with self.subTest(stdout=stdout):
                self.assertFalse(check_claude_package.validation_summary(stdout)["passed"])
        good["manifest"]["errors"] = ["bad manifest"]
        result = check_claude_package.validation_summary(json.dumps(good))
        self.assertFalse(result["passed"])
        self.assertEqual(result["error_count"], 1)

    def test_resolved_targets_are_recorded_and_wrong_target_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "release-inventory.json").write_text("{}")
            def invoke(command, **kwargs):
                path = Path(command[-1])
                target = path if path.suffix == ".json" else path / ".claude-plugin/marketplace.json"
                return subprocess.CompletedProcess(command, 0, json.dumps(self.payload(target, target.stem)), "")
            with patch.object(check_claude_package.subprocess, "check_output", return_value="test CLI"), \
                 patch.object(check_claude_package.subprocess, "run", side_effect=invoke):
                report = check_claude_package.check(root, root / "evidence")
            self.assertTrue(report["passed"])
            self.assertEqual(len(report["validated_targets"]), 2)
            self.assertEqual(report["checks"][0]["validation"]["type"], "marketplace")
            self.assertEqual(report["checks"][0]["validation"]["warning_count"], 0)
            wrong = subprocess.CompletedProcess([], 0, json.dumps(self.payload("/elsewhere/plugin.json")), "")
            with patch.object(check_claude_package.subprocess, "check_output", return_value="test CLI"), \
                 patch.object(check_claude_package.subprocess, "run", return_value=wrong):
                report = check_claude_package.check(root, root / "wrong")
            self.assertFalse(report["passed"])

    def test_missing_input_is_recorded_as_failure_without_starting_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(check_claude_package.subprocess, "check_output") as cli:
                report = check_claude_package.check(root / "missing", root / "evidence")
            cli.assert_not_called()
            self.assertFalse(report["passed"])
            self.assertIn("error", report)
