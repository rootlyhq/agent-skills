"""Regression tests for the static checker; these do not exercise an LLM."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import build_skills
import validate_skills


class StaticValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rootly-skills-validation-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("skills", "tools/templates", "tools/tests/behavior"):
            shutil.copytree(ROOT / folder, self.root / folder)
        shutil.copyfile(ROOT / "VERSION", self.root / "VERSION")
        for module in (build_skills, validate_skills):
            patcher = patch.object(module, "ROOT", self.root)
            patcher.start()
            self.addCleanup(patcher.stop)

    def change(self, relative, old, new):
        path = self.root / relative
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def check_error(self, fragment):
        errors, _, _ = validate_skills.validate()
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_current_tree_passes(self):
        errors, _, _ = validate_skills.validate()
        self.assertEqual(errors, [])

    def scenario_cases(self):
        path = self.root / "tools/tests/behavior/cases.json"
        return path, json.loads(path.read_text())

    def test_adding_valid_pair_passes(self):
        path, cases = self.scenario_cases()
        original = cases[0]
        contrast = next(case for case in cases if case["id"] == original["contrast"])
        cases.extend([
            {**original, "id": "new-case", "contrast": "new-counterpart"},
            {**contrast, "id": "new-counterpart", "contrast": "new-case"},
        ])
        path.write_text(json.dumps(cases))
        errors, _, _ = validate_skills.validate()
        self.assertEqual(errors, [])

    def test_generated_reference_drift_fails(self):
        self.change("skills/on-call/references/common.md", "Shared operating rules", "Drift")
        self.check_error("generated resource drift")

    def test_conditional_reference_drift_fails(self):
        self.change("skills/on-call/references/responder-judgment.md", "# Responder judgment", "# Drift")
        self.check_error("generated resource drift")

    def test_version_drift_fails(self):
        current = (self.root / "VERSION").read_text().strip()
        self.change("skills/on-call/SKILL.md", f'version: "{current}"', 'version: "9.9"')
        self.check_error("version drift")

    def test_missing_reference_fails(self):
        (self.root / "skills/on-call/references/output.md").unlink()
        self.check_error("missing references/output.md")

    def test_cross_skill_link_fails(self):
        self.change("skills/on-call/SKILL.md", "references/output.md", "../deploy-check/SKILL.md")
        self.check_error("nonportable link")

    def test_write_mapping_fails(self):
        self.change("skills/on-call/references/tools.md", "| read |", "| write |")
        self.check_error("non-read tool")

    def test_authoring_rejects_other_write_tools(self):
        self.change("skills/skill-authoring/references/tools.md",
                    "`create_ai_skill` | write", "`update_ai_skill` | write")
        self.check_error("non-read tool")

    def test_authoring_cannot_label_creation_as_a_read(self):
        self.change("skills/skill-authoring/references/tools.md", "| write |", "| read |")
        self.check_error("non-read tool")

    def test_authoring_access_metadata_is_explicit(self):
        self.change("skills/skill-authoring/SKILL.md", "access: write", "access: read")
        self.check_error("access must be write")

    def test_nonportable_frontmatter_fails(self):
        self.change("skills/on-call/SKILL.md", "license: Apache-2.0", "disable-model-invocation: true\nlicense: Apache-2.0")
        self.check_error("frontmatter keys")

    def test_private_path_fails(self):
        self.change("skills/on-call/SKILL.md", "# On-call", "# On-call\nPrivate source: /Users/example/input.md")
        self.check_error("private source reference")

    def test_invalid_contrast_fails(self):
        path, cases = self.scenario_cases()
        cases[0]["contrast"] = "not-a-case"
        path.write_text(json.dumps(cases))
        self.check_error("invalid counterexample link")

    def test_nonreciprocal_contrast_fails(self):
        path, cases = self.scenario_cases()
        cases[0]["contrast"] = next(case["id"] for case in cases
                                   if case["skill"] == cases[0]["skill"]
                                   and case["id"] not in (cases[0]["id"], cases[0]["contrast"]))
        path.write_text(json.dumps(cases))
        self.check_error("contrast must be reciprocal")

    def test_cross_skill_contrast_fails(self):
        path, cases = self.scenario_cases()
        other = next(case for case in cases if case["skill"] != cases[0]["skill"])
        cases[0]["contrast"], other["contrast"] = other["id"], cases[0]["id"]
        path.write_text(json.dumps(cases))
        self.check_error("contrast must use the same skill")

    def test_identical_contrast_evidence_fails(self):
        path, cases = self.scenario_cases()
        other = next(case for case in cases if case["id"] == cases[0]["contrast"])
        other["facts"] = list(reversed(cases[0]["facts"]))
        path.write_text(json.dumps(cases))
        self.check_error("contrast must change the supplied evidence")

    def test_identical_contrast_expectations_fail(self):
        path, cases = self.scenario_cases()
        other = next(case for case in cases if case["id"] == cases[0]["contrast"])
        other["must"] = cases[0]["must"]
        path.write_text(json.dumps(cases))
        self.check_error("contrast must change the required reasoning or decision")

    def test_missing_contrast_reason_fails(self):
        path, cases = self.scenario_cases()
        del cases[0]["contrast_reason"]
        path.write_text(json.dumps(cases))
        self.check_error("contrast_reason")


if __name__ == "__main__":
    unittest.main()
