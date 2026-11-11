import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import prepare_release_assets as assets
import prepare_release_pr as release_pr
import verify_release_candidate as candidate
from test_release_metadata import write_tree


class ReleasePreparationTests(unittest.TestCase):
    def test_generated_release_preserves_curated_notes_and_syncs_all_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_tree(root)
            skill = root / "skills/example/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text('---\nmetadata:\n  version: "1.0.0"\n---\nKeep these instructions.\n')
            (root / "VERSION").write_text("1.2.3\n")
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## [1.2.3](https://example.com/compare) (2026-11-11)\n\n"
                "### Features\n\n- Generated entry.\n\n## 1.2.3 — unreleased\n\n"
                "- Curated migration guidance.\n\n## 1.0 — 2026-10-16\n\n- Historical.\n")
            with patch.object(release_pr.bump_version, "regenerate") as generate:
                self.assertEqual(release_pr.prepare(root), "1.2.3")
                generate.assert_called_once()
                first = (root / "CHANGELOG.md").read_text()
                release_pr.prepare(root)
            self.assertEqual((root / "CHANGELOG.md").read_text(), first)
            self.assertIn("- Curated migration guidance.", first)
            self.assertIn("- Generated entry.", first)
            self.assertIn("## 1.0 — 2026-10-16", first)
            self.assertNotIn("unreleased", first)
            self.assertIn('version: "1.2.3"', skill.read_text())
            self.assertTrue(skill.read_text().endswith("Keep these instructions.\n"))
            self.assertEqual(release_pr.metadata.problems(root, released=True), [])

    def test_mismatched_release_header_is_rejected_before_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_tree(root)
            before = (root / "CHANGELOG.md").read_bytes()
            with self.assertRaises(ValueError):
                release_pr.prepare(root)
            self.assertEqual((root / "CHANGELOG.md").read_bytes(), before)

    def test_reviewed_archive_hash_is_required_before_any_assets_are_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "candidate.zip"
            archive.write_bytes(b"reviewed zip")
            (root / "release-inventory.json").write_text('{"file":"hash"}')
            package = {"archive": str(archive), "directory": str(root)}
            for bad in ("", "g" * 64, "0" * 64):
                with self.assertRaises(ValueError):
                    assets.assemble(package, "v1.2.3", bad, root / "refused")
                self.assertFalse((root / "refused").exists())
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            assets.assemble(package, "v1.2.3", digest, root / "release")
            self.assertEqual((root / "release/rootly-v1.2.3.zip").read_bytes(), archive.read_bytes())
            self.assertEqual((root / "release/rootly-v1.2.3.zip.sha256").read_text(),
                             digest + "  rootly-v1.2.3.zip\n")


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "tag.gpgsign", "false")
        self.git("config", "commit.gpgsign", "false")
        (self.root / "VERSION").write_text("1.2.3\n")
        (self.root / ".release-please-manifest.json").write_text('{".":"1.2.3"}')
        self.commit("chore(release): v1.2.3")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.sha)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True,
                                       stderr=subprocess.DEVNULL).strip()

    def commit(self, subject):
        self.git("add", "-A")
        self.git("commit", "--allow-empty", "-qm", subject)

    def test_exact_main_release_commit_is_accepted(self):
        self.assertEqual(candidate.verify(self.sha, self.root),
                         {"sha": self.sha, "version": "1.2.3", "tag": "v1.2.3"})

    def test_branch_name_or_wrong_subject_cannot_publish(self):
        with self.assertRaises(ValueError):
            candidate.verify("main", self.root)
        self.commit("fix: unrelated")
        sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", sha)
        with self.assertRaises(ValueError):
            candidate.verify(sha, self.root)

    def test_off_main_candidate_is_rejected(self):
        self.commit("chore(release): v1.2.3")
        with self.assertRaises(subprocess.CalledProcessError):
            candidate.verify(self.git("rev-parse", "HEAD"), self.root)

    def test_tag_cannot_move_but_same_commit_can_resume(self):
        self.git("tag", "v1.2.3", self.sha)
        candidate.verify(self.sha, self.root)
        self.commit("chore(release): v1.2.3")
        sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", sha)
        with self.assertRaisesRegex(ValueError, "immutable"):
            candidate.verify(sha, self.root)

    def test_manifest_must_agree_with_version(self):
        (self.root / ".release-please-manifest.json").write_text('{".":"1.2.2"}')
        self.commit("chore(release): v1.2.3")
        sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", sha)
        with self.assertRaisesRegex(ValueError, "manifest"):
            candidate.verify(sha, self.root)


class WorkflowBoundaryTests(unittest.TestCase):
    def load(self, name):
        return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)

    def test_publishing_is_manual_and_approval_follows_preparation(self):
        workflow = self.load("release.yml")
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow["jobs"]["publish"]["environment"], "release")
        self.assertEqual(workflow["jobs"]["publish"]["needs"], "prepare")
        self.assertEqual(workflow["permissions"]["contents"], "read")
        self.assertEqual(workflow["on"]["workflow_dispatch"]["inputs"]["fidelity_reviewed"]["default"], "false")
        for job in workflow["jobs"].values():
            self.assertEqual(job["runs-on"], "blacksmith-2vcpu-ubuntu-2404")

    def test_bot_prepares_prs_without_tagging_and_explicitly_dispatches_ci(self):
        workflow = self.load("release-please.yml")
        steps = workflow["jobs"]["release-pr"]["steps"]
        action = next(s for s in steps if s.get("uses", "").startswith("googleapis/release-please-action@"))
        self.assertEqual(action["with"]["skip-github-release"], "true")
        self.assertTrue(any('gh workflow run validate.yml --ref "$RELEASE_BRANCH"' in s.get("run", "") for s in steps))
        config = json.loads((ROOT / "release-please-config.json").read_text())
        self.assertEqual(config["packages"]["."]["version-file"], "VERSION")
        self.assertEqual(config["pull-request-title-pattern"], "chore(release): v${version}")
