"""Repeated tests retain separate evidence, actual model identity and old failures."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from collect_claude_results import collect as collect_claude
from collect_workflow_results import collect as collect_wire
from run_workflow_probes import probe_folder


class ResultCollectionTests(unittest.TestCase):
    def test_repeat_folders_do_not_collide_with_each_other_or_legacy(self):
        paths = {probe_folder(Path("results"), "claude", "case", repeat)
                 for repeat in [None, 1, 2, 3]}
        self.assertEqual(len(paths), 4)

    def test_wire_repeats_preserve_failures_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for repeat in [1, 2, 3]:
                path = probe_folder(root, "codex", "case", repeat)
                path.mkdir()
                (path / "result.json").write_text(json.dumps({"client": "codex", "case": "case",
                    "repeat": repeat, "mechanics": {"passed": repeat != 1}}))
            self.assertEqual(collect_wire(root), 3)
            collected = json.loads((root / "collected-results.json").read_text())
            self.assertFalse(collected[0]["mechanics"]["passed"])
            with self.assertRaises(FileExistsError):
                collect_wire(root)

    def test_duplicate_legacy_and_first_repeat_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, extra in [("old", {}), ("new", {"repeat": 1})]:
                (root / name).mkdir()
                (root / name / "result.json").write_text(json.dumps({"client": "codex", "case": "case", **extra}))
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                collect_wire(root)
            self.assertFalse((root / "collected-results.json").exists())

    def test_claude_records_actual_model_not_just_initialization_label(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            trace = root / "trace.jsonl"
            trace.write_text("\n".join(json.dumps(e) for e in [
                {"type": "system", "subtype": "init", "model": "configured-alias", "claude_code_version": "fixture"},
                {"type": "assistant", "message": {"model": "actual-model"}},
                {"type": "result", "result": "synthetic answer"}]))
            report = root / "report.json"
            report.write_text(json.dumps({"cases": [{"name": "case", "arms": {"with": [
                {"tracePath": str(trace), "passed": False, "graders": [{"name": "failure", "passed": False}]}]}}]}))
            with patch("builtins.print"):
                collect_claude(report, root / "collected")
            result = json.loads((root / "collected/summary.json").read_text())[0]
            self.assertEqual(result["message_models"], ["actual-model"])
            self.assertEqual(result["initialization_model"], "configured-alias")
            self.assertFalse(result["automatic_pass"])
            self.assertFalse(result["common_loaded"])
            self.assertEqual((root / "collected/case-with-0.jsonl").read_bytes(), trace.read_bytes())
