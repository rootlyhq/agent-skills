"""Commit-message convention checks. These do not exercise an LLM."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import check_commit_messages as messages

GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


class SubjectTests(unittest.TestCase):
    def test_valid_subjects(self):
        for subject in ("feat: add alert grouping evidence", "fix(on-call): keep handoff gaps visible",
                        "docs(install): clarify Codex setup", "feat(skills)!: rename deploy-check outputs",
                        "chore(release): v1.1.0", "ci: pin setup-python", "fix: handle MCP timeouts"):
            self.assertEqual(messages.subject_problems(subject), [], subject)

    def test_missing_type_fails(self):
        self.assertTrue(messages.subject_problems("Add alert grouping"))

    def test_unknown_type_fails(self):
        self.assertIn("unknown type", messages.subject_problems("feature: add grouping")[0])

    def test_trailing_period_fails(self):
        self.assertIn("period", messages.subject_problems("fix: handle timeouts.")[0])

    def test_capitalized_summary_fails(self):
        self.assertIn("capital", messages.subject_problems("fix: Handle timeouts")[0])

    def test_acronym_start_passes(self):
        self.assertEqual(messages.subject_problems("fix: MCP timeouts no longer hide errors"), [])

    def test_long_subject_fails(self):
        self.assertIn("longer than", messages.subject_problems("fix: " + "x" * 80)[0])

    def test_uppercase_scope_fails(self):
        self.assertTrue(messages.subject_problems("fix(On-Call): keep gaps"))

    def test_release_subject(self):
        self.assertEqual(messages.release_subject("1.1.0"), "chore(release): v1.1.0")


class RangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rootly-commit-messages-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        return subprocess.run([*GIT, *args], cwd=self.root, check=True, capture_output=True, text=True).stdout

    def commit(self, subject, body=""):
        (self.root / "file.txt").write_text(subject + body)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", subject + ("\n\n" + body if body else ""))

    def test_range_lists_each_commit(self):
        self.commit("feat: first")
        self.commit("Bad subject", "body line")
        found = messages.commits("HEAD~1..HEAD", self.root)
        self.assertEqual([subject for _, subject, _ in found], ["Bad subject"])
        self.assertEqual(found[0][2].strip(), "body line")

    def test_release_check_reads_tagged_commit(self):
        self.commit("chore(release): v1.0.0")
        self.git("tag", "-a", "v1.0.0", "-m", "v1.0.0")
        with patch.object(messages, "ROOT", self.root), patch.object(sys, "argv", ["x", "--release", "v1.0.0"]):
            self.assertEqual(messages.main(), 0)
        self.commit("feat: later")
        self.git("tag", "-a", "v1.1.0", "-m", "v1.1.0")
        with patch.object(messages, "ROOT", self.root), patch.object(sys, "argv", ["x", "--release", "v1.1.0"]):
            self.assertEqual(messages.main(), 1)


if __name__ == "__main__":
    unittest.main()
