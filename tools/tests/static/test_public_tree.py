"""Every candidate is scanned; only exact private-marker literals are exempt."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import check_public_tree
import export_release


class PublicTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="public-tree-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = patch.object(export_release, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        environment = patch.dict(os.environ, {"ROOTLY_SKILLS_PRIVATE_MARKERS": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def scan(self, files):
        for name, text in files.items():
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(text)
        return check_public_tree.findings(self.root, list(files))

    def test_clean_files_pass(self):
        self.assertEqual(self.scan({"README.md": "Seven read-only skills."}), [])

    def test_local_path_fails(self):
        self.assertEqual(self.scan({"docs/notes.md": "See /" + "Users/someone/input.md"}),
                         [("docs/notes.md", "private marker on line 1")])

    def test_planning_file_name_fails(self):
        name = "IMPLEMENTATION" + "_PLAN.md"
        self.assertEqual(self.scan({name: "plan"}), [(name, "private path")])

    def test_local_markers_apply(self):
        (self.root / ".private-markers").write_text("ExamplePerson\n")
        self.assertEqual(self.scan({"docs/a.md": "Thanks to ExamplePerson"}), [("docs/a.md", "private marker on line 1")])

    def test_credentials_fail(self):
        self.assertTrue(self.scan({"config.json": "ghp_" + "a" * 30}))

    def test_only_exact_reviewed_lines_are_exempt(self):
        name = "tools/scripts/validate_skills.py"
        line = next(line for line in (ROOT / name).read_text().splitlines()
                    if "practitioner-" + "workbook" in line)
        self.assertEqual(self.scan({name: line}), [])
        self.assertTrue(self.scan({name: line + " extra"}))
        self.assertTrue(self.scan({"other.py": line}))

    def test_credentials_in_formerly_exempt_file_are_rejected(self):
        self.assertTrue(self.scan({"tools/scripts/validate_skills.py": "ghp_" + "a" * 30}))

    def test_case_variations_are_rejected(self):
        for marker in ("/" + "users/example/input.md", "implementation" + "_plan.md"):
            self.assertTrue(self.scan({"docs/a.md": marker}))

    def test_binary_and_symlink_candidates_fail_closed(self):
        path = self.root / "fixture.bin"
        for content in (b"\xffprivate", b"text\x00binary"):
            path.write_bytes(content)
            self.assertTrue(check_public_tree.findings(self.root, [path.name]))
        link = self.root / "link.md"
        link.symlink_to(path)
        self.assertTrue(check_public_tree.findings(self.root, [link.name]))

    def test_ci_requires_and_uses_private_markers(self):
        with self.assertRaisesRegex(ValueError, "required"):
            check_public_tree.findings(self.root, [], require_private=True)
        with patch.dict(os.environ, {"ROOTLY_SKILLS_PRIVATE_MARKERS": "ExamplePerson"}):
            self.assertTrue(self.scan({"docs/a.md": "exampleperson"}))
            self.assertEqual(check_public_tree.findings(self.root, [], require_private=True), [])

    def test_multiline_private_marker_is_not_missed(self):
        with patch.dict(os.environ, {"ROOTLY_SKILLS_PRIVATE_MARKERS": r"Example\s+Person"}):
            self.assertTrue(self.scan({"docs/a.md": "Example\nPerson"}))

    def test_invalid_marker_regex_is_reported_without_its_value(self):
        with patch.dict(os.environ, {"ROOTLY_SKILLS_PRIVATE_MARKERS": "private-value["}):
            with self.assertRaises(ValueError) as error:
                check_public_tree.findings(self.root, [])
            self.assertNotIn("private-value", str(error.exception))

    def test_current_tree_is_clean(self):
        with patch.object(export_release, "ROOT", ROOT):
            self.assertEqual(check_public_tree.findings(ROOT), [])


if __name__ == "__main__":
    unittest.main()
