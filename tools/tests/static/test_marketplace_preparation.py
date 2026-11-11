import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import prepare_marketplace_bundle as preparation

CATALOG_SHA = "b" * 40


class MarketplacePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "export.zip"
        self.plugin = {
            "name": "rootly", "version": "1.2.3", "description": "Read-only incident workflows.",
            "homepage": preparation.REPOSITORY, "repository": preparation.REPOSITORY,
            "extensions": {"com.openai": {"interface": {"displayName": "Rootly"}}},
        }
        self.files = {
            "VERSION": b"1.2.3\n", "CHANGELOG.md": b"## 1.2.3 \xe2\x80\x94 unreleased\n\n- Changes.\n",
            "plugin.json": preparation.encoded(self.plugin),
            ".claude-plugin/plugin.json": preparation.encoded(
                {"name": "rootly", "version": "1.2.3", "author": {"name": "Rootly"}}),
            "adapters/read-tools.json": preparation.encoded({"skills": {
                s: ["get_incident"] for s in ("incident-response", "alert-triage", "deploy-check", "on-call", "retrospective")}}),
        }
        self.catalog = json.dumps({"plugins": [
            {"name": "unrelated", "description": "Preserve this entry"},
            {"name": "rootly", "description": "Old description", "category": "monitoring",
             "source": {"source": "url", "url": "https://example.com/previous.git"},
             "commands": ["legacy"], "hooks": {"old": "override"}},
            {"name": "another", "source": "./another"},
        ]}, indent=2) + "\n"
        self.source = self.root / "source"
        self.source.mkdir()
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com"), ("commit.gpgsign", "false")):
            subprocess.run(["git", "config", key, value], cwd=self.source, check=True)
        self.commit_files()
        self.write_archive()

    def commit_files(self):
        for name, content in self.files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        subprocess.run(["git", "add", "-A"], cwd=self.source, check=True)
        subprocess.run(["git", "commit", "-qm", "test: synthetic release"], cwd=self.source, check=True)
        self.sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.source, text=True).strip()

    def write_archive(self, *, extra=None, duplicate=False):
        self.inventory = preparation.encoded({n: hashlib.sha256(c).hexdigest() for n, c in self.files.items()})
        with zipfile.ZipFile(self.archive, "w") as bundle:
            for name, content in {**self.files, "release-inventory.json": self.inventory}.items():
                bundle.writestr("export/" + name, content)
            if extra:
                bundle.writestr(extra, b"unlisted")
            if duplicate:
                with self.assertWarns(UserWarning):
                    bundle.writestr("export/VERSION", b"1.2.3\n")
        self.export = {"archive": str(self.archive), "sha256": preparation.digest(self.archive.read_bytes())}

    def prepare(self, directory="prepared", **kwargs):
        return preparation.prepare(self.export, "v1.2.3", self.sha, self.catalog, CATALOG_SHA,
                                   self.root / directory, preview=kwargs.pop("preview", True), root=self.source, **kwargs)

    def test_bundle_keeps_exact_plugin_and_inventory_and_is_deterministic(self):
        manifest, first = self.prepare()
        _, second = self.prepare("again")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(manifest["plugin_archive_sha256"], self.export["sha256"])
        self.assertEqual(manifest["candidate_sha"], self.sha)
        with zipfile.ZipFile(first) as bundle:
            self.assertEqual(bundle.read(manifest["plugin_archive"]), self.archive.read_bytes())
            self.assertEqual(bundle.read("release-inventory.json"), self.inventory)
            checks = bundle.read("SHA256SUMS").decode().splitlines()
            self.assertEqual(len(checks), len(bundle.namelist()) - 1)
            for line in checks:
                digest, name = line.split("  ", 1)
                self.assertEqual(preparation.digest(bundle.read(name)), digest)
            self.assertNotIn(str(self.root).encode(), bundle.read("release.json"))

    def test_patch_applies_without_changing_other_entries_or_carrying_legacy_overrides(self):
        self.prepare()
        checkout = self.root / "catalog"
        target = checkout / ".claude-plugin/marketplace.json"
        target.parent.mkdir(parents=True)
        target.write_text(self.catalog)
        subprocess.run(["git", "init", "-q", str(checkout)], check=True)
        patch = self.root / "prepared/claude/catalog.patch"
        subprocess.run(["git", "apply", "--unidiff-zero", str(patch)], cwd=checkout, check=True)
        before, after = json.loads(self.catalog)["plugins"], json.loads(target.read_text())["plugins"]
        self.assertEqual(before[0], after[0])
        self.assertEqual(before[2], after[2])
        self.assertEqual(after[1]["source"]["sha"], self.sha)
        self.assertEqual(after[1]["source"]["url"], preparation.REPOSITORY + ".git")
        self.assertEqual(after[1]["description"], self.plugin["description"])
        self.assertNotIn("commands", after[1])
        self.assertNotIn("hooks", after[1])
        self.assertNotIn("unrelated", patch.read_text())
        self.assertNotIn('"another"', patch.read_text())

    def test_missing_or_duplicate_rootly_listing_requires_review_before_output(self):
        for plugins in ([], [{"name": "rootly"}, {"name": "rootly"}]):
            self.catalog = json.dumps({"plugins": plugins})
            with self.assertRaisesRegex(ValueError, "exactly one"):
                self.prepare()
            self.assertFalse((self.root / "prepared").exists())

    def test_self_consistent_export_cannot_be_mislabeled_with_another_commit(self):
        self.files["CHANGELOG.md"] += b"An uncommitted change.\n"
        self.write_archive()
        with self.assertRaisesRegex(ValueError, "differs from candidate"):
            self.prepare()
        self.assertFalse((self.root / "prepared").exists())

    def test_duplicate_catalog_keys_are_rejected_before_writing(self):
        self.catalog = '{"plugins":[],"plugins":[{"name":"rootly"}]}'
        with self.assertRaisesRegex(ValueError, "Duplicate key"):
            self.prepare()
        self.assertFalse((self.root / "prepared").exists())

    def test_wrong_hash_is_rejected_before_writing(self):
        self.export["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.prepare()
        self.assertFalse((self.root / "prepared").exists())

    def test_unlisted_duplicate_and_escaping_archive_members_are_rejected(self):
        for kwargs in ({"extra": "export/unlisted.txt"}, {"extra": "export/../escape"}, {"duplicate": True}):
            self.write_archive(**kwargs)
            with self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse((self.root / "prepared").exists())

    def test_bad_sha_or_mismatched_version_is_rejected_before_output(self):
        for sha in ("main", "A" * 40, "a" * 39):
            with self.assertRaises(ValueError):
                preparation.prepare(self.export, "v1.2.3", sha, self.catalog, CATALOG_SHA,
                                    self.root / "prepared", preview=True)
        with self.assertRaisesRegex(ValueError, "versions differ"):
            preparation.read_package(self.export, "v1.2.4")
        self.assertFalse((self.root / "prepared").exists())

    def test_unreleased_metadata_is_preview_only_and_dated_release_has_final_names(self):
        with self.assertRaisesRegex(ValueError, "dated"):
            self.prepare(preview=False)
        self.assertFalse((self.root / "prepared").exists())
        self.files["CHANGELOG.md"] = "## 1.2.3 — 2026-11-11\n\n- Changes.\n".encode()
        self.commit_files()
        self.write_archive()
        manifest, bundle = self.prepare(preview=False)
        self.assertEqual(bundle.name, "rootly-marketplaces-v1.2.3.zip")
        self.assertEqual(manifest["plugin_archive"], "rootly-v1.2.3.zip")

    def test_previews_and_review_materials_cannot_claim_submission_or_test_success(self):
        manifest, bundle = self.prepare()
        self.assertEqual(manifest["stage"], "preview")
        self.assertIn("PREVIEW — NOT A RELEASE", (bundle.parent / "README.md").read_text())
        worksheet = json.loads((bundle.parent / "openai/review-cases.json").read_text())
        self.assertEqual(len(worksheet["positive"]), 5)
        self.assertEqual(len(worksheet["negative"]), 3)
        self.assertTrue(all(not case["executed"] for case in worksheet["positive"] + worksheet["negative"]))
        self.assertTrue(any("supportURL" in item for item in manifest["pending"]))
        self.assertEqual(json.loads((bundle.parent / "openai/listing.json").read_text()),
                         self.plugin["extensions"]["com.openai"]["interface"])
        self.assertIn("No provider submission", preparation.summary(manifest))
        with self.assertRaises(FileExistsError):
            self.prepare()


class PreparationWorkflowTests(unittest.TestCase):
    def load(self, name):
        return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)

    def test_release_pr_previews_have_read_only_permissions_and_no_provider_writes(self):
        workflow = self.load("validate.yml")
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job = workflow["jobs"]["marketplace-preview"]
        self.assertEqual(job["needs"], "static")
        self.assertIn("release-please--", job["if"])
        self.assertEqual(job["runs-on"], "blacksmith-2vcpu-ubuntu-2404")
        prepare = next(s for s in job["steps"] if "prepare_marketplace_bundle.py" in s.get("run", ""))
        self.assertIn("--preview", prepare["run"])
        self.assertNotIn("gh pr create", prepare["run"])
        self.assertNotIn("git push", prepare["run"])
        upload = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
        self.assertEqual(upload["with"]["name"], "marketplace-preparation")

    def test_final_bundle_is_prepared_before_approval_and_publish_uses_prepared_bytes(self):
        workflow = self.load("release.yml")
        prepare = workflow["jobs"]["prepare"]["steps"]
        index = next(i for i, s in enumerate(prepare) if "prepare_marketplace_bundle.py" in s.get("run", ""))
        self.assertTrue(any(s.get("uses", "").startswith("actions/upload-artifact@") for s in prepare[index + 1:]))
        publish = workflow["jobs"]["publish"]
        self.assertEqual(publish["environment"], "release")
        commands = "\n".join(s.get("run", "") for s in publish["steps"])
        self.assertIn('"release/marketplaces/rootly-marketplaces-$TAG.zip"', commands)
        self.assertLess(commands.index("sha256sum --check \"rootly-marketplaces"), commands.index("git push origin"))
        self.assertNotIn("prepare_marketplace_bundle.py", commands)
        self.assertNotIn("gh pr create", commands)
