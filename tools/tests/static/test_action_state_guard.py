"""Meaningful invariants at the proposed host boundary; no model calls."""

import copy
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
sys.path.insert(0, str(ROOT / "tools/tests/fixtures"))
from action_state_cases import APPROVAL_ONLY, RETAINED_FAILURE_CLAIM, evidence, fact
from action_state_guard import STATES, Invalid, check, evaluate, model_evidence, parse_json


def candidate(approval="approved", execution="unknown", approval_ids=None, execution_ids=None):
    return {"snapshot_id": APPROVAL_ONLY["snapshot_id"], "action_id": "mitigation-1",
            "approval": {"state": approval, "evidence_ids": ["approval-1"] if approval_ids is None else approval_ids},
            "execution": {"state": execution, "evidence_ids": [] if execution_ids is None else execution_ids}}


class ActionStateGuardTests(unittest.TestCase):
    def test_retained_failure_annotation_is_rejected(self):
        result = evaluate(APPROVAL_ONLY, RETAINED_FAILURE_CLAIM)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["errors"], ["execution:unsupported_state"])
        self.assertIsNone(result["rendered"])

    def test_approval_does_not_determine_any_execution_state(self):
        for execution in STATES["execution"]:
            with self.subTest(execution=execution):
                result = evaluate(APPROVAL_ONLY, candidate(execution=execution))
                self.assertEqual(result["accepted"], execution == "unknown")

    def test_all_independent_states_require_matching_evidence(self):
        # Exhaust all 16 host state combinations and all 16 proposed combinations.
        for approval, execution in itertools.product(*STATES.values()):
            facts = []
            if approval != "unknown":
                facts.append(fact("approval-1", "approval", approval))
            if execution != "unknown":
                facts.append(fact("execution-1", "execution", execution))
            for a, e in itertools.product(*STATES.values()):
                proposal = candidate(a, e, [] if a == "unknown" else ["approval-1"],
                                     [] if e == "unknown" else ["execution-1"])
                with self.subTest(host=(approval, execution), proposed=(a, e)):
                    self.assertEqual(evaluate(evidence(*facts), proposal)["accepted"],
                                     (a, e) == (approval, execution))

    def test_explicit_nonexecution_is_allowed_not_a_banned_phrase(self):
        ledger = evidence(*APPROVAL_ONLY["facts"], fact("execution-1", "execution", "not_started"))
        self.assertTrue(evaluate(ledger, candidate(execution="not_started", execution_ids=["execution-1"]))["accepted"])

    def test_execution_does_not_imply_approval(self):
        ledger = evidence(fact("execution-1", "execution", "in_progress"))
        self.assertTrue(evaluate(ledger, candidate("unknown", "in_progress", [], ["execution-1"]))["accepted"])
        self.assertFalse(evaluate(ledger, candidate("approved", "in_progress", ["execution-1"], ["execution-1"]))["accepted"])

    def test_conflict_cannot_be_hidden_by_cherry_picking(self):
        ledger = evidence(*APPROVAL_ONLY["facts"], fact("x", "execution", "not_started"),
                          fact("y", "execution", "in_progress", source_id="RESPONDER2"))
        self.assertTrue(evaluate(ledger, candidate())["accepted"])
        self.assertFalse(evaluate(ledger, candidate(execution="not_started", execution_ids=["x"]))["accepted"])

    def test_excluded_stale_and_other_action_records_cannot_support_a_claim(self):
        for override in ({"eligibility": "stale"}, {"eligibility": "not_authorized"}, {"action_id": "other-action"}):
            ledger = evidence(*APPROVAL_ONLY["facts"], fact("x", "execution", "not_started", **override))
            with self.subTest(override=override):
                self.assertEqual(model_evidence(ledger)["facts"], APPROVAL_ONLY["facts"])
                self.assertTrue(evaluate(ledger, candidate())["accepted"])
                self.assertFalse(evaluate(ledger, candidate(execution="not_started", execution_ids=["x"]))["accepted"])

    def test_wrong_field_and_fabricated_citations_rejected(self):
        ledger = evidence(*APPROVAL_ONLY["facts"], fact("x", "execution", "completed"))
        for ids in ([], ["approval-1"], ["invented"], ["x", "invented"], ["x", "x"]):
            self.assertFalse(evaluate(ledger, candidate(execution="completed", execution_ids=ids))["accepted"])

    def test_known_state_cannot_be_hidden_as_unknown(self):
        self.assertFalse(evaluate(APPROVAL_ONLY, candidate(approval="unknown", approval_ids=[]))["accepted"])

    def test_snapshot_and_action_binding(self):
        for field in ("snapshot_id", "action_id"):
            item = candidate()
            item[field] = "another-snapshot-or-action"
            self.assertFalse(evaluate(APPROVAL_ONLY, item)["accepted"])

    def test_no_prose_or_self_supplied_evidence_escape_hatch(self):
        for key in ("explanation", "rendered", "evidence", "recovery", "notes"):
            item = candidate()
            item[key] = "CANARY_UNCHECKED: action is not yet run"
            result = evaluate(APPROVAL_ONLY, item)
            self.assertFalse(result["accepted"])
            self.assertNotIn("CANARY_UNCHECKED", json.dumps(result))

    def test_unknown_requires_no_positive_citations(self):
        self.assertFalse(evaluate(APPROVAL_ONLY, candidate(execution_ids=["approval-1"]))["accepted"])

    def test_rendering_comes_from_host_and_does_not_claim_success(self):
        ledger = evidence(*APPROVAL_ONLY["facts"], fact("x", "execution", "completed"),
                          fact("y", "execution", "completed", source_id="LOG1"))
        first = evaluate(ledger, candidate(execution="completed", execution_ids=["x"]))
        second = evaluate(ledger, candidate(execution="completed", execution_ids=["y"]))
        self.assertTrue(first["accepted"])
        self.assertEqual(first["rendered"], second["rendered"])
        self.assertIn("as reported", first["rendered"])
        self.assertIn("not independent verification of recovery", first["rendered"])

    def test_input_shapes_fail_closed(self):
        for item in (None, [], {}, {**candidate(), "execution": None},
                     {**candidate(), "execution": {"state": "unknown", "evidence_ids": "x"}}):
            self.assertFalse(evaluate(APPROVAL_ONLY, item)["accepted"])

    def test_invalid_host_snapshot_fails_closed(self):
        for change in ({"version": True}, {"as_of": "yesterday"}, {"as_of": "2026-02-30T12:00:00Z"},
                       {"facts": APPROVAL_ONLY["facts"] * 2}, {"label": "line\nbreak"}):
            self.assertFalse(evaluate({**APPROVAL_ONLY, **change}, candidate())["accepted"])

    def test_duplicate_keys_nonfinite_and_raw_prose_rejected(self):
        for text in ('{"execution":1,"execution":2}', '{"a":NaN}', "Approved and not yet run."):
            with self.assertRaises(Invalid):
                parse_json(text)

    def test_oversized_integer_returns_a_json_rejection_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence.json").write_text(json.dumps(APPROVAL_ONLY))
            (root / "candidate.json").write_text('{"a":' + '1' * 5000 + '}')
            result = subprocess.run([sys.executable, str(ROOT / "tools/scripts/action_state_guard.py"),
                "--evidence", str(root / "evidence.json"), "--candidate", str(root / "candidate.json")],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["accepted"])
            self.assertNotIn("Traceback", result.stderr)

    def test_unicode_control_labels_rejected_without_rejecting_normal_unicode(self):
        for character in ("\x7f", "\x85", "\u202e", "\u2028", "\u2029", "\ud800"):
            with self.subTest(character=repr(character)):
                self.assertFalse(evaluate({**APPROVAL_ONLY, "label": "Action" + character}, candidate())["accepted"])
        self.assertTrue(evaluate({**APPROVAL_ONLY, "label": "Rétablissement 東京"}, candidate())["accepted"])

    def test_guard_does_not_mutate_evidence_or_candidate(self):
        ledger, item = copy.deepcopy(APPROVAL_ONLY), candidate()
        before = copy.deepcopy((ledger, item))
        check(ledger, item)
        self.assertEqual((ledger, item), before)

    def test_cli_rejects_without_printing_untrusted_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence.json").write_text(json.dumps(APPROVAL_ONLY))
            (root / "candidate.json").write_text(json.dumps({**candidate(), "notes": "CANARY_BAD"}))
            command = [sys.executable, str(ROOT / "tools/scripts/action_state_guard.py"),
                       "--evidence", str(root / "evidence.json"), "--candidate", str(root / "candidate.json")]
            rejected = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 1)
            self.assertFalse(json.loads(rejected.stdout)["accepted"])
            self.assertNotIn("CANARY_BAD", rejected.stdout)
            (root / "candidate.json").write_text(json.dumps(candidate()))
            accepted = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(accepted.returncode, 0)
            self.assertTrue(json.loads(accepted.stdout)["accepted"])


if __name__ == "__main__":
    unittest.main()
