"""Offline release-coverage tests. No native client or judge calls."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import fidelity_gate as gate
import fidelity_judge as judge
import fidelity_matrix as matrix


class MatrixTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.package = self.root / "package"
        self.package.mkdir()
        (self.package / "VERSION").write_text("test")
        (self.package / "release-inventory.json").write_text(json.dumps({"VERSION": hashlib.sha256(b"test").hexdigest()}))
        self.runs = self.root / "runs"
        self.runs.mkdir()

    def populate(self, **kwargs):
        manifest = matrix.manifest(self.package, **kwargs)
        (self.runs / "matrix-manifest.json").write_text(json.dumps(manifest))
        for arm in manifest["arms"]:
            client, model = arm.split("-", 1)
            for case in manifest["cases"]:
                for repeat in range(1, manifest["repetitions"] + 1):
                    folder = self.runs / arm / f"{client}-{case}-run-{repeat:02d}"
                    folder.mkdir(parents=True)
                    (folder / "result.json").write_text(json.dumps({
                        "client": client, "case": case, "repeat": repeat, "model": "test-model",
                        "requested_model": model if client == "claude" else None,
                        "package_inventory_sha256": manifest["package_inventory_sha256"]}))
        return manifest

    def test_full_matrix_has_exact_coverage(self):
        self.populate()
        folders, errors = matrix.validate(self.runs, self.package)
        self.assertFalse(errors)
        self.assertEqual(len(folders), len(matrix.ARMS) * len(matrix.RELEASE_CASES) * 3)

    def test_empty_matrix_fails_without_judge_calls(self):
        with patch.object(judge, "judge") as model:
            result = gate.grade(self.runs, 3, "fable", 1, self.package)
        self.assertFalse(result["passed"])
        self.assertIn("empty_matrix", result["errors"])
        model.assert_not_called()

    def test_missing_and_duplicate_runs_are_rejected(self):
        self.populate()
        first = next(self.runs.rglob("result.json"))
        duplicate = first.parent / "duplicate"
        duplicate.mkdir()
        first.rename(duplicate / "result.json")
        self.assertIn("matrix_missing_or_unexpected_results", matrix.validate(self.runs, self.package)[1])

    def test_subset_and_too_few_repetitions_are_not_release_clearance(self):
        self.populate(arms=[matrix.ARMS[0]], cases=[matrix.RELEASE_CASES[0]], repetitions=1)
        self.assertIn("release_requires_all_arms_cases_and_three_repetitions", matrix.validate(self.runs, self.package)[1])

    def test_package_and_result_identity_are_bound(self):
        self.populate()
        first = next(self.runs.rglob("result.json"))
        result = json.loads(first.read_text())
        result.update(case="wrong-case", package_inventory_sha256="wrong-package")
        first.write_text(json.dumps(result))
        errors = matrix.validate(self.runs, self.package)[1]
        self.assertTrue(any(e.startswith("result_identity_mismatch") for e in errors))
        self.assertTrue(any(e.startswith("result_package_mismatch") for e in errors))

    def test_modified_package_and_evidence_are_rejected(self):
        self.populate()
        (self.package / "VERSION").write_text("changed")
        self.assertIn("package_content_changed", matrix.validate(self.runs, self.package)[1])
        with patch.object(judge, "scenario_evidence", return_value="changed evidence"):
            self.assertIn("matrix_manifest_or_evidence_changed", matrix.validate(self.runs, self.package)[1])

    def test_stale_calibration_blocks_even_complete_matrix(self):
        self.populate()
        with patch.object(judge, "calibration_errors", return_value=["calibration_stale:judge_sha256"]), \
                patch.object(gate, "grade_run") as grade_run:
            result = gate.grade(self.runs, 3, "fable", 1, self.package)
        self.assertFalse(result["passed"])
        grade_run.assert_not_called()

    def test_complete_matrix_is_graded_when_calibration_is_current(self):
        self.populate()
        def passed(folder, *_):
            result = json.loads((folder / "result.json").read_text())
            return {**result, "gate": "pass"}
        with patch.object(judge, "calibration_errors", return_value=[]), patch.object(gate, "grade_run", side_effect=passed):
            result = gate.grade(self.runs, 3, "fable", 1, self.package)
        self.assertTrue(result["passed"])

    def test_existing_grade_is_not_overwritten(self):
        (self.runs / "gate.json").write_text("retained result")
        with self.assertRaises(FileExistsError):
            gate.grade(self.runs, 3, "fable", 1, self.package)
        self.assertEqual((self.runs / "gate.json").read_text(), "retained result")

    def test_invalid_matrix_arguments_rejected(self):
        for kwargs in ({"arms": []}, {"arms": ["claude-fable", "claude-fable"]},
                       {"cases": ["typo"]}, {"repetitions": 0}, {"repetitions": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                matrix.manifest(self.package, **kwargs)
