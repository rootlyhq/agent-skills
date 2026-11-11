"""Release-notes composition. These do not exercise an LLM."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import release_notes
from test_release_metadata import write_tree

GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


class ReleaseNotesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rootly-release-notes-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_tree(self.root)
        self.archive = self.root / "rootly-v1.0.zip"
        self.archive.write_bytes(b"zip bytes")

    def git(self, *args):
        return subprocess.run([*GIT, *args], cwd=self.root, check=True, capture_output=True, text=True).stdout

    def test_first_release_notes(self):
        notes = release_notes.compose("v1.0", self.archive, None, None, self.root)
        self.assertIn("## What's new\n\n- First entry.", notes)
        self.assertIn("## Changed\n\nSkills: all seven (first release).", notes)
        self.assertNotIn("compare/", notes)
        self.assertIn("claude plugin marketplace add rootlyhq/agent-skills", notes)
        self.assertIn("`rootly-v1.0.zip` · SHA-256 `", notes)

    def test_later_release_lists_changed_skills_and_diff(self):
        paths = ["skills/on-call/SKILL.md", "skills/alert-triage/references/tools.md", "docs/install.md", "README.md"]
        notes = release_notes.compose("v1.0", self.archive, "v0.9", paths, self.root)
        self.assertIn("## Changed since v0.9\n\nSkills: alert-triage, on-call\nAlso: README.md, docs", notes)
        self.assertIn("https://github.com/rootlyhq/agent-skills/compare/v0.9...v1.0", notes)

    def test_unchanged_skills_say_so(self):
        self.assertEqual(release_notes.changed_summary(["docs/install.md"]), "Skills: unchanged\nAlso: docs")

    def test_tag_must_match_version(self):
        with self.assertRaises(ValueError):
            release_notes.compose("v1.0.1", self.archive, None, None, self.root)

    def test_previous_tag_from_git_history(self):
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "first")
        self.git("tag", "-a", "v0.9", "-m", "v0.9")
        (self.root / "docs/install.md").write_text("changed\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "second")
        self.git("tag", "-a", "v1.0", "-m", "v1.0")
        self.assertEqual(release_notes.previous_tag("v1.0", self.root), "v0.9")
        self.assertIsNone(release_notes.previous_tag("v0.9", self.root))
        self.assertEqual(release_notes.changed_paths("v1.0", "v0.9", self.root), ["docs/install.md"])


if __name__ == "__main__":
    unittest.main()
