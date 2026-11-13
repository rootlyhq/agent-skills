import hashlib
import io
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
import build_microsoft_package as microsoft
import check_public_tree
import export_release
import microsoft_manifest
import release_notes
from public_assets import reviewed_binary


class MicrosoftPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = export_release.release_files()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root = self.directory / "source"
        self.root.mkdir()
        self.files = dict(self.template)
        self.version = self.files["VERSION"].decode().strip()
        self.tag = "v" + self.version
        self.git("init", "-q")
        self.candidate, self.export = self.commit_export()
        self.output = self.directory / "microsoft"

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
            cwd=self.root, stderr=subprocess.DEVNULL, text=True,
        ).strip()

    def commit_export(self):
        for name, content in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.git("add", ".")
        self.git("commit", "-qm", "test: package fixture")
        return self.git("rev-parse", "HEAD"), self.write_export()

    def write_export(self):
        inventory = {name: hashlib.sha256(content).hexdigest()
                     for name, content in self.files.items()}
        files = {**self.files, "release-inventory.json": json.dumps(inventory).encode()}
        archive = self.directory / "export.zip"
        archive.write_bytes(microsoft.archive_bytes({f"rootly/{n}": c for n, c in files.items()}))
        return {"archive": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}

    def prepare(self, **kwargs):
        return microsoft.prepare(self.export, self.tag, self.candidate, self.output,
                                 root=self.root, **kwargs)

    def test_exact_skills_root_layout_and_reproducible_bytes(self):
        inventory, archive = self.prepare(preview=True)
        expected = microsoft.package_files(self.files, self.version)
        with zipfile.ZipFile(archive) as bundle:
            actual = {name: bundle.read(name) for name in bundle.namelist()}
            self.assertEqual(actual, expected)
            self.assertEqual(json.loads(actual["manifest.json"])["version"], self.version)
            for name, content in actual.items():
                if name.startswith("skills/"):
                    self.assertEqual(content, self.files[name])
        self.assertEqual(archive.read_bytes(), microsoft.archive_bytes(expected))
        self.assertEqual(inventory["sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(inventory["candidate_sha"], self.candidate)
        self.assertEqual(inventory["source_archive_sha256"], self.export["sha256"])
        self.assertFalse(inventory["submitted"])
        self.assertEqual(inventory["provider_validation"], "pending")
        self.assertIn("PREVIEW", (self.output / "README.md").read_text())
        self.assertFalse(any("HANDOFF" in name for name in actual))

    def test_release_notes_identify_both_packages_and_microsoft_checksum(self):
        _, archive = self.prepare(preview=True)
        notes = release_notes.compose(self.tag, Path(self.export["archive"]), None, [],
                                      root=self.root, microsoft_archive=archive)
        self.assertIn(archive.name, notes)
        self.assertIn(hashlib.sha256(archive.read_bytes()).hexdigest(), notes)
        self.assertIn("does not establish marketplace availability", notes)

    def test_stable_app_dcr_url_and_separate_default_connection(self):
        manifest = json.loads(self.files["adapters/microsoft/manifest.json"])
        self.assertEqual(manifest, microsoft_manifest.manifest(self.version))
        self.assertEqual(manifest["id"], "c819ab41-e86d-479e-94e5-30bf776f8691")
        remote = manifest["agentConnectors"][0]["toolSource"]["remoteMcpServer"]
        self.assertEqual(remote, {"mcpServerUrl": "https://mcp.rootly.com/mcp?toolsets=all"})
        for name in ("mcp.json", ".mcp.json"):
            self.assertIn("readonly=true", self.files[name].decode())

    def test_manifest_or_missing_skill_drift_is_rejected(self):
        manifest = json.loads(self.files["adapters/microsoft/manifest.json"])
        for key, value in (("id", "changed"), ("version", "0.0.0"), ("agentConnectors", [])):
            with self.subTest(key=key):
                files = {**self.files, "adapters/microsoft/manifest.json":
                         json.dumps({**manifest, key: value}).encode()}
                with self.assertRaises(ValueError):
                    microsoft.package_files(files, self.version)
        files = dict(self.files)
        del files["skills/on-call/SKILL.md"]
        with self.assertRaisesRegex(ValueError, "Missing Microsoft skill"):
            microsoft.package_files(files, self.version)

    def test_new_workflow_does_not_silently_gain_a_connection(self):
        files = {**self.files, "skills/skill-authoring/SKILL.md": b"not approved for this adapter"}
        selected = microsoft.package_files(files, self.version)
        self.assertNotIn("skills/skill-authoring/SKILL.md", selected)
        self.assertEqual(sum(name.endswith("/SKILL.md") for name in selected), 7)

    def test_reviewed_icons_only_and_tampering_rejected(self):
        for name in ("color.png", "outline.png"):
            path = "assets/microsoft/" + name
            content = self.files[path]
            self.assertTrue(reviewed_binary(path, content))
            self.assertEqual(check_public_tree.content_findings(path, content, export_release.private_pattern()), [])
            self.assertTrue(check_public_tree.content_findings("other/" + name, content,
                                                              export_release.private_pattern()))
            for changed in (content + b"hidden content", b"arbitrary replacement"):
                self.assertTrue(check_public_tree.content_findings(path, changed,
                                                                  export_release.private_pattern()))
                with self.assertRaises(ValueError):
                    microsoft.package_files({**self.files, path: changed}, self.version)

    def test_index_and_commit_scans_accept_only_exact_branding_blobs(self):
        self.assertEqual(check_public_tree.git_findings(self.root, staged=True), [])
        self.assertEqual(check_public_tree.git_findings(self.root, revision_range=self.candidate), [])
        path = self.root / "assets/microsoft/color.png"
        path.write_bytes(path.read_bytes() + b"hidden")
        self.git("add", "assets/microsoft/color.png")
        self.assertTrue(check_public_tree.git_findings(self.root, staged=True))

    def test_source_and_export_hash_are_checked_before_output(self):
        self.export["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.prepare(preview=True)
        self.assertFalse(self.output.exists())
        self.files["skills/on-call/SKILL.md"] += b"\nchanged\n"
        self.export = self.write_export()
        with self.assertRaisesRegex(ValueError, "differs from candidate"):
            self.prepare(preview=True)
        self.assertFalse(self.output.exists())

    def test_unreviewed_or_wrong_microsoft_hash_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "reviewed artifact"):
            self.prepare(preview=True, expected="0" * 64)
        self.assertFalse(self.output.exists())
        self.files["CHANGELOG.md"] = self.files["CHANGELOG.md"].replace(b"unreleased", b"2026-11-12", 1)
        self.candidate, self.export = self.commit_export()
        with self.assertRaisesRegex(ValueError, "reviewed Microsoft"):
            self.prepare()
        self.assertFalse(self.output.exists())
        expected = hashlib.sha256(microsoft.archive_bytes(
            microsoft.package_files(self.files, self.version))).hexdigest()
        inventory, archive = self.prepare(expected=expected)
        self.assertEqual(archive.name, f"rootly-microsoft-{self.tag}.zip")
        self.assertEqual(inventory["stage"], "release-preparation")
        self.assertEqual(inventory["sha256"], expected)

    def test_unreleased_or_bad_candidate_cannot_be_finalized(self):
        with self.assertRaisesRegex(ValueError, "dated release"):
            self.prepare(expected="0" * 64)
        with self.assertRaisesRegex(ValueError, "40-character"):
            microsoft.prepare(self.export, self.tag, "main", self.output, preview=True, root=self.root)
        self.assertFalse(self.output.exists())

    def test_duplicate_unsafe_or_uninventoried_members_are_rejected(self):
        original = Path(self.export["archive"]).read_bytes()
        for name in ("../escape", "rootly/unlisted.txt", "rootly/VERSION"):
            with self.subTest(name=name):
                stream = io.BytesIO(original)
                with zipfile.ZipFile(stream, "a") as bundle:
                    bundle.writestr(name, b"unreviewed")
                Path(self.export["archive"]).write_bytes(stream.getvalue())
                self.export["sha256"] = hashlib.sha256(stream.getvalue()).hexdigest()
                with self.assertRaises(ValueError):
                    self.prepare(preview=True)
                self.assertFalse(self.output.exists())


class MicrosoftWorkflowTests(unittest.TestCase):
    def load(self, name):
        return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)

    def test_preview_is_read_only_and_uploads_a_labeled_package(self):
        workflow = self.load("validate.yml")
        job = workflow["jobs"]["microsoft-preview"]
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(job["needs"], "static")
        steps = job["steps"]
        runs = "\n".join(step.get("run", "") for step in steps)
        self.assertIn("--preview", runs)
        self.assertIn("--candidate", runs)
        self.assertEqual(steps[-1]["with"]["name"], "microsoft-package-preview")
        self.assertNotIn("secrets.", json.dumps(job))
        self.assertNotIn("gh release", runs)

    def test_exact_microsoft_bytes_are_prepared_before_release_approval(self):
        workflow = self.load("release.yml")
        inputs = workflow["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["expected_microsoft_archive_sha256"]["required"], "true")
        prepare = workflow["jobs"]["prepare"]
        publish = workflow["jobs"]["publish"]
        self.assertEqual(publish["environment"], "release")
        prep_runs = "\n".join(step.get("run", "") for step in prepare["steps"])
        pub_runs = "\n".join(step.get("run", "") for step in publish["steps"])
        self.assertIn("build_microsoft_package.py", prep_runs)
        self.assertIn('--expected-sha256 "$EXPECTED_MICROSOFT_SHA256"', prep_runs)
        self.assertNotIn("build_microsoft_package.py", pub_runs)
        self.assertIn('"release/microsoft/rootly-microsoft-$TAG.zip" | sha256sum --check', pub_runs)
        self.assertIn('"release/microsoft/rootly-microsoft-$TAG-inventory.json"', pub_runs)
        self.assertNotIn("atk ", pub_runs)


if __name__ == "__main__":
    unittest.main()
