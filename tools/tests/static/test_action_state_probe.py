"""The host boundary must withhold unsupported candidates and free-form prose."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
sys.path.insert(0, str(ROOT / "tools/tests/fixtures"))
import run_action_state_probe as probe
from action_state_cases import CASES, RETAINED_FAILURE_CLAIM


def good_candidate():
    item = copy.deepcopy(RETAINED_FAILURE_CLAIM)
    item["execution"] = {"state": "unknown", "evidence_ids": []}
    return item


class ActionStateProbeTests(unittest.TestCase):
    def test_codex_commentary_cannot_become_checked_output(self):
        def message(phase, text):
            return {"method": "item/completed", "params": {"item": {
                "type": "agentMessage", "phase": phase, "text": text}}}
        events = [message("commentary", "Unchecked: approved and not yet run"),
                  message("final_answer", json.dumps(good_candidate()))]
        self.assertEqual(probe.codex_result(events), good_candidate())
        with self.assertRaises(ValueError):
            probe.codex_result(events + [events[-1]])
        with self.assertRaises(ValueError):
            probe.codex_result(events[:1])
        with self.assertRaises(ValueError):
            probe.codex_result([message("final_answer", "Some prose " + json.dumps(good_candidate()))])

    def test_claude_requires_structured_result_and_actual_model(self):
        events = [{"type": "assistant", "message": {"model": "claude-test"}},
                  {"type": "result", "subtype": "success", "structured_output": good_candidate(),
                   "result": "Unchecked: approved and not yet run"}]
        self.assertEqual(probe.claude_result(events), (good_candidate(), "claude-test"))
        with self.assertRaises(ValueError):
            probe.claude_result(events[1:])
        with self.assertRaises(ValueError):
            probe.claude_result(events + [events[-1]])
        events[-1]["is_error"] = True
        with self.assertRaises(ValueError):
            probe.claude_result(events)
        del events[-1]["is_error"]
        del events[-1]["structured_output"]
        with self.assertRaises(ValueError):
            probe.claude_result(events)

    def run_mock(self, folder, candidate=None, failure=None):
        package = folder / "package"
        package.mkdir()
        (package / "release-inventory.json").write_text("{}")
        output = folder / "output"
        output.mkdir()
        with patch.object(probe, "run_claude", side_effect=failure,
                          return_value=(candidate, "claude-test", True)), \
             patch.object(probe.subprocess, "check_output", return_value="test CLI"):
            result = probe.run("claude", CASES[0], package, output, "fable")
        return result, output / "claude-approval-only"

    def test_unsupported_native_candidate_never_reaches_display(self):
        with tempfile.TemporaryDirectory() as directory:
            result, folder = self.run_mock(Path(directory), RETAINED_FAILURE_CLAIM)
            self.assertEqual(result["status"], "completed")
            self.assertFalse(result["accepted"])
            self.assertIn("withheld", (folder / "display.md").read_text())
            self.assertNotIn("not_started", result["display"])
            self.assertEqual(json.loads((folder / "candidate.json").read_text()), RETAINED_FAILURE_CLAIM)

    def test_success_displays_only_the_validated_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            result, folder = self.run_mock(Path(directory), good_candidate())
            self.assertTrue(result["accepted"])
            self.assertIn("Execution status unknown", result["display"])
            self.assertEqual(result["display"], json.loads((folder / "validation.json").read_text())["rendered"])
            self.assertEqual(result["model_identity_source"], "assistant_message")

    def test_codex_model_is_labeled_as_thread_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package").mkdir()
            (root / "package/release-inventory.json").write_text("{}")
            (root / "output").mkdir()
            with patch.object(probe, "run_codex", return_value=(good_candidate(), "configured-model", True)), \
                 patch.object(probe.subprocess, "check_output", return_value="test CLI"):
                result = probe.run("codex", CASES[0], root / "package", root / "output", "fable")
            self.assertTrue(result["accepted"])
            self.assertEqual(result["model"], "configured-model")
            self.assertEqual(result["model_identity_source"], "thread_start")

    def test_timeout_fails_closed_without_a_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            result, folder = self.run_mock(Path(directory), failure=TimeoutError("fixture"))
            self.assertEqual(result["status"], "error")
            self.assertFalse(result["accepted"])
            self.assertIn("withheld", (folder / "display.md").read_text())
            self.assertFalse((folder / "candidate.json").exists())

    def test_excluded_evidence_not_sent_to_model(self):
        case = copy.deepcopy(CASES[0])
        case["evidence"]["facts"][0].update(eligibility="not_authorized", source_id="PRIVATE_CANARY")
        prompt = probe.prompt_for(case)
        self.assertNotIn("PRIVATE_CANARY", prompt)

    def test_unknown_case_cannot_silently_reduce_requested_coverage(self):
        with self.assertRaises(ValueError):
            probe.select_cases(["approval-only", "approvl-only"])
        self.assertEqual([c["id"] for c in probe.select_cases(["approval-only"])], ["approval-only"])

    def test_missing_cli_is_retained_as_a_per_case_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package").mkdir()
            (root / "package/release-inventory.json").write_text("{}")
            (root / "output").mkdir()
            with patch.object(probe.subprocess, "check_output", side_effect=FileNotFoundError("fixture missing CLI")):
                result = probe.run("codex", CASES[0], root / "package", root / "output", "fable")
            self.assertEqual(result["status"], "error")
            self.assertFalse(result["accepted"])
            self.assertEqual(json.loads((root / "output/codex-approval-only/result.json").read_text()), result)
            for name in ("evidence", "prompt", "schema", "guard", "package_inventory"):
                self.assertRegex(result[name + "_sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn("client_version", result)

    def test_existing_case_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "claude-approval-only").mkdir()
            original = root / "claude-approval-only/result.json"
            original.write_text("original result")
            result = probe.run("claude", CASES[0], root / "absent-package", root, "fable")
            self.assertEqual(result["status"], "error")
            self.assertEqual(original.read_text(), "original result")


if __name__ == "__main__":
    unittest.main()
