"""Version bump and release marking. These do not exercise an LLM."""

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import build_package
import build_skills
import bump_version
import check_release_metadata as metadata
from test_release_metadata import write_tree


class BumpVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rootly-bump-version-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("skills", "tools/templates", "tools/tests/behavior"):
            shutil.copytree(ROOT / folder, self.root / folder)
        write_tree(self.root)
        for skill in (self.root / "skills").glob("*/SKILL.md"):
            text = re.sub(r'version: "[^"]+"', 'version: "1.0"', skill.read_text(), count=1)
            skill.write_text(text)
        for module in (build_skills, build_package, bump_version):
            patcher = patch.object(module, "ROOT", self.root)
            patcher.start()
            self.addCleanup(patcher.stop)

    def changelog(self):
        return (self.root / "CHANGELOG.md").read_text()

    def test_bump_moves_every_reference(self):
        self.assertEqual(bump_version.bump("1.1", self.root), "1.1")
        self.assertEqual((self.root / "VERSION").read_text(), "1.1\n")
        self.assertIn("## 1.1 — unreleased", self.changelog())
        self.assertNotIn("## 1.0", self.changelog())
        self.assertIn("`1.1`", (self.root / "README.md").read_text())
        self.assertTrue((self.root / "docs/migration.md").read_text().startswith("# Migration to 1.1\n"))
        for skill in (self.root / "skills").glob("*/SKILL.md"):
            self.assertIn('version: "1.1"', skill.read_text(), skill.parent.name)
        manifest = json.loads((self.root / ".cursor-plugin/plugin.json").read_text())
        self.assertEqual(manifest["version"], "1.1")
        self.assertEqual(metadata.problems(self.root), [])

    def test_bump_after_release_opens_new_section(self):
        write_tree(self.root, state="2026-10-16")
        bump_version.bump("1.1", self.root)
        self.assertIn("## 1.1 — unreleased\n\n## 1.0 — 2026-10-16\n", self.changelog())

    def test_bump_rejects_non_increasing_version(self):
        for version in ("1.0", "0.9", "0.1"):
            with self.assertRaises(ValueError, msg=version):
                bump_version.bump(version, self.root)
        self.assertEqual((self.root / "VERSION").read_text(), "1.0\n")

    def test_allow_downgrade_resets_before_first_release(self):
        self.assertEqual(bump_version.bump("0.1", self.root, allow_downgrade=True), "0.1")
        self.assertEqual((self.root / "VERSION").read_text(), "0.1\n")
        self.assertIn("## 0.1 — unreleased", self.changelog())
        self.assertEqual(metadata.problems(self.root), [])

    def test_allow_downgrade_still_rejects_same_version(self):
        with self.assertRaises(ValueError):
            bump_version.bump("1.0", self.root, allow_downgrade=True)

    def test_bump_rejects_malformed_version(self):
        for version in ("1.1.0", "1.1-rc.1", "v1.1"):
            with self.assertRaises(ValueError, msg=version):
                bump_version.bump(version, self.root)

    def test_release_dates_the_top_section(self):
        self.assertEqual(bump_version.release(self.root, today="2026-10-16"), "v1.0")
        self.assertIn("## 1.0 — 2026-10-16", self.changelog())
        self.assertEqual(metadata.problems(self.root, released=True), [])

    def test_release_twice_fails(self):
        bump_version.release(self.root, today="2026-10-16")
        with self.assertRaises(ValueError):
            bump_version.release(self.root, today="2026-10-17")

    def test_release_requires_entries(self):
        write_tree(self.root, entries="")
        with self.assertRaises(ValueError):
            bump_version.release(self.root, today="2026-10-16")


if __name__ == "__main__":
    unittest.main()
