"""Version-metadata consistency checks. These do not exercise an LLM."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import check_release_metadata as metadata


def write_tree(root, version="1.0.0", state="unreleased", entries="- First entry.\n"):
    (root / "VERSION").write_text(version + "\n")
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## {version} — {state}\n\n{entries}\n## 0.9.0 — 2025-06-01\n\n- Older.\n")
    (root / "README.md").write_text(f"# Title\n\n## Status\n\n`{version}` — first public release.\n")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs/migration.md").write_text(f"# Migration to {version}\n\nText.\n")


class ReleaseMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rootly-release-metadata-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_tree(self.root)

    def change(self, relative, old, new):
        path = self.root / relative
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def assert_problem(self, fragment, **kwargs):
        errors = metadata.problems(self.root, **kwargs)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_repository_tree_is_consistent(self):
        self.assertEqual(metadata.problems(ROOT), [])

    def test_consistent_fixture_passes(self):
        self.assertEqual(metadata.problems(self.root), [])

    def test_changelog_version_mismatch_fails(self):
        self.change("CHANGELOG.md", "## 1.0.0", "## 1.1.0")
        self.assert_problem("top section is 1.1.0")

    def test_readme_drift_fails(self):
        self.change("README.md", "`1.0.0`", "`0.9.0`")
        self.assert_problem("README.md")

    def test_migration_title_drift_fails(self):
        self.change("docs/migration.md", "# Migration to 1.0.0", "# Migration to 1.1.0")
        self.assert_problem("docs/migration.md")

    def test_invalid_version_fails(self):
        (self.root / "VERSION").write_text("1\n")
        self.assert_problem("Invalid version")

    def test_malformed_heading_fails(self):
        self.change("CHANGELOG.md", "## 0.9.0 — 2025-06-01", "## 0.9.0")
        self.assert_problem("every '## ' heading")

    def test_older_unreleased_section_fails(self):
        self.change("CHANGELOG.md", "## 0.9.0 — 2025-06-01", "## 0.9.0 — unreleased")
        self.assert_problem("not the top section")

    def test_released_requires_date(self):
        self.assert_problem("still marked unreleased", released=True)

    def test_released_requires_entries(self):
        write_tree(self.root, state="2026-10-16", entries="")
        self.assert_problem("has no entries", released=True)

    def test_dated_section_with_entries_passes_released_check(self):
        write_tree(self.root, state="2026-10-16")
        self.assertEqual(metadata.problems(self.root, released=True, tag="v1.0.0"), [])

    def test_tag_must_match_version(self):
        self.assert_problem("Tag v1.1.0 does not match v1.0.0", tag="v1.1.0")

    def test_notes_are_the_top_section_body(self):
        self.assertEqual(metadata.notes(self.root), "- First entry.")

    def test_version_ordering(self):
        ordered = ["0.9.0", "1.0.0", "1.0.1", "1.0.2", "1.0.10", "1.1.0", "1.2.0", "2.0.0", "10.0.0"]
        parsed = [metadata.parse_version(v) for v in ordered]
        self.assertEqual(parsed, sorted(parsed))
        self.assertEqual(len(set(parsed)), len(parsed))

    def test_version_parse_rejects_other_suffixes(self):
        for bad in ("1.0", "01.0.0", "1.0.0-rc.1", "1.0.0-beta.1", "v1.0.0", "1", "1.0.0.1"):
            with self.assertRaises(ValueError, msg=bad):
                metadata.parse_version(bad)


if __name__ == "__main__":
    unittest.main()
