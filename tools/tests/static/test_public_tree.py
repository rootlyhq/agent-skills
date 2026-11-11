"""Every candidate is scanned; only exact private-marker literals are exempt."""

import os
import subprocess
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

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL, text=True)

    def init_git(self):
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.test")
        (self.root / "README.md").write_text("Clean baseline.")
        self.git("add", ".")
        self.git("commit", "-qm", "test: baseline")
        return self.git("rev-parse", "HEAD").strip()

    def test_staged_scan_reads_index_instead_of_clean_worktree(self):
        self.init_git()
        path = self.root / "README.md"
        path.write_text("ghp_" + "a" * 30)
        self.git("add", ".")
        path.write_text("Clean working copy.")
        self.assertEqual(check_public_tree.findings(self.root), [])
        findings = check_public_tree.git_findings(self.root, staged=True)
        self.assertTrue(any("credential marker" in reason for _, reason in findings))
        self.assertNotIn("a" * 30, repr(findings))

    def test_clean_index_is_not_confused_with_dirty_worktree(self):
        self.init_git()
        (self.root / "README.md").write_text("ghp_" + "a" * 30)
        self.assertEqual(check_public_tree.git_findings(self.root, staged=True), [])
        self.assertTrue(check_public_tree.findings(self.root))

    def test_local_replace_refs_cannot_hide_published_blob_contents(self):
        self.init_git()
        (self.root / "README.md").write_text("ghp_" + "a" * 30)
        self.git("add", ".")
        oid = self.git("rev-parse", ":README.md").strip()
        clean = subprocess.check_output(["git", "hash-object", "-w", "--stdin"], cwd=self.root,
                                        input="Sanitized replacement.", text=True).strip()
        self.git("replace", oid, clean)
        self.assertTrue(check_public_tree.git_findings(self.root, staged=True))

    def test_range_scan_finds_private_content_removed_before_head(self):
        base = self.init_git()
        path = self.root / "removed.md"
        path.write_text("ghp_" + "a" * 30)
        self.git("add", ".")
        self.git("commit", "-qm", "test: intermediate")
        self.git("rm", "-q", path.name)
        self.git("commit", "-qm", "test: remove")
        self.assertEqual(check_public_tree.git_findings(self.root, revision_range="HEAD^..HEAD"), [])
        findings = check_public_tree.git_findings(self.root, revision_range=base + "..HEAD")
        self.assertTrue(any("removed.md" in name and "credential marker" in reason for name, reason in findings))

    def test_git_scan_rejects_symlinks_and_unmerged_index(self):
        self.init_git()
        (self.root / "link.md").symlink_to("README.md")
        self.git("add", ".")
        self.assertTrue(check_public_tree.git_findings(self.root, staged=True))
        self.git("reset", "-q", "HEAD")
        oid = self.git("rev-parse", "HEAD:README.md").strip()
        subprocess.run(["git", "update-index", "--index-info"], cwd=self.root,
                       input=f"0 {'0' * 40}\tREADME.md\n100644 {oid} 1\tREADME.md\n",
                       text=True, check=True)
        self.assertTrue(any("unmerged" in reason for _, reason in
                            check_public_tree.git_findings(self.root, staged=True)))

    def test_git_scans_use_configured_markers_and_exact_exemptions(self):
        self.init_git()
        name = "tools/scripts/validate_skills.py"
        line = next(line for line in (ROOT / name).read_text().splitlines()
                    if "practitioner-" + "workbook" in line)
        (self.root / name).parent.mkdir(parents=True)
        (self.root / name).write_text(line + "\n")
        self.git("add", ".")
        self.assertEqual(check_public_tree.git_findings(self.root, staged=True), [])
        with patch.dict(os.environ, {"ROOTLY_SKILLS_PRIVATE_MARKERS": "Clean baseline"}):
            self.assertTrue(check_public_tree.git_findings(self.root, staged=True, require_private=True))

    def test_invalid_git_range_fails_closed(self):
        self.init_git()
        with self.assertRaises(subprocess.CalledProcessError):
            check_public_tree.git_findings(self.root, revision_range="missing-ref..HEAD")

    def test_optional_hooks_scan_staged_and_every_pushed_range(self):
        import json
        executable = self.root / "fake-python"
        output = self.root / "hook-arguments"
        executable.write_text("#!" + sys.executable + "\nimport json, sys\n"
                              + "from pathlib import Path\n"
                              + f"with Path({str(output)!r}).open('a') as stream:\n"
                              + "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n")
        executable.chmod(0o755)
        environment = dict(os.environ, ROOTLY_SKILLS_PYTHON=str(executable))
        subprocess.run(["sh", str(ROOT / ".githooks/pre-commit")], cwd=self.root, env=environment, check=True)
        zeros, old, new = "0" * 40, "1" * 40, "2" * 40
        pushed = (f"refs/heads/a {new} refs/heads/a {old}\n"
                  f"refs/heads/b {new} refs/heads/b {zeros}\n"
                  f"(delete) {zeros} refs/heads/c {old}\n")
        subprocess.run(["sh", str(ROOT / ".githooks/pre-push")], cwd=self.root, env=environment,
                       input=pushed, text=True, check=True)
        calls = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(calls, [
            ["tools/scripts/check_public_tree.py", "--staged", "--require-private-markers"],
            ["tools/scripts/check_public_tree.py", "--range", old + ".." + new, "--require-private-markers"],
            ["tools/scripts/check_public_tree.py", "--range", new, "--require-private-markers"],
        ])

    def test_current_tree_is_clean(self):
        with patch.object(export_release, "ROOT", ROOT):
            self.assertEqual(check_public_tree.findings(ROOT), [])


if __name__ == "__main__":
    unittest.main()
