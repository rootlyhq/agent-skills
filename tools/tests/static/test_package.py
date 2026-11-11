"""Packaging/privacy regressions. These do not prove model behavior."""

import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import build_evals
import build_package
import build_skills
import export_release


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rootly-package-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "source"
        self.root.mkdir()
        for folder in ("skills", "tools/templates", "adapters"):
            shutil.copytree(ROOT / folder, self.root / folder)
        for name in export_release.TOP_FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        for module in (build_skills, build_package, export_release):
            patcher = patch.object(module, "ROOT", self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.output = self.root.parent / "dist"

    def test_generated_package_matches(self):
        for path, expected in build_package.generated_files():
            self.assertEqual(path.read_text(), expected, str(path))

    def test_codex_plugin_restriction_uses_full_plugin_id(self):
        """Codex ignores plugin server settings keyed by the bare plugin name."""
        files = dict(build_package.generated_files())
        toml = files[self.root / "adapters/codex/readonly.toml"]
        self.assertIn('[plugins."rootly@rootly-agent-skills".mcp_servers.rootly]', toml)
        self.assertNotIn('[plugins."rootly".mcp_servers.rootly]', toml)
        self.assertIn("[mcp_servers.rootly]", toml)

    def test_bundled_connections_request_server_readonly(self):
        """All client formats request read-only mode without narrowing skill coverage."""
        import tomllib
        from urllib.parse import parse_qs, urlsplit

        files = dict(build_package.generated_files())
        urls = [
            json.loads(files[self.root / name])["mcpServers"]["rootly"]["url"]
            for name in ("mcp.json", ".mcp.json")
        ]
        profile = tomllib.loads(files[self.root / "adapters/codex/readonly.toml"])
        urls.append(profile["mcp_servers"]["rootly"]["url"])
        import yaml
        for path, content in files.items():
            if path.name == "openai.yaml":
                urls.extend(tool["url"] for tool in yaml.safe_load(content)["dependencies"]["tools"])
        self.assertEqual(len(urls), 3 + len(list((self.root / "skills").glob("*/SKILL.md"))))
        for url in urls:
            with self.subTest(url=url):
                parsed = urlsplit(url)
                self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                                 ("https", "mcp.rootly.com", "/mcp"))
                self.assertEqual(parse_qs(parsed.query),
                                 {"toolsets": ["all"], "readonly": ["true"]})

    def test_codex_listing_metadata_meets_directory_limits(self):
        """Codex reads presentation from extensions.com.openai; the public directory caps each field."""
        files = dict(build_package.generated_files())
        root = json.loads(files[self.root / "plugin.json"])
        interface = root["extensions"]["com.openai"]["interface"]
        self.assertLessEqual(len(interface["displayName"]), 30)
        self.assertLessEqual(len(interface["shortDescription"]), 30)
        self.assertLessEqual(len(interface["longDescription"]), 4000)
        self.assertLessEqual(len(interface["developerName"]), 80)
        self.assertTrue(interface["category"])
        self.assertTrue(0 < len(interface["capabilities"]) <= 20)
        self.assertTrue(all(len(item) <= 120 for item in interface["capabilities"]))
        self.assertTrue(0 < len(interface["defaultPrompt"]) <= 3)
        self.assertTrue(all(len(item) <= 128 for item in interface["defaultPrompt"]))
        self.assertTrue(interface["websiteURL"].startswith("https://"))
        for key in ("logo", "composerIcon"):
            self.assertTrue(interface[key].startswith("./"), key)
            self.assertTrue((self.root / interface[key]).is_file(), key)

    def test_claude_allowlist_covers_connector_namespace(self):
        """With a claude.ai Rootly connector present, the plugin server is suppressed and its tools are renamed."""
        files = dict(build_package.generated_files())
        allowed = json.loads(files[self.root / "adapters/claude/readonly.settings.json"])["permissions"]["allow"]
        for namespace in ("rootly", "plugin_rootly_rootly", "claude_ai_Rootly"):
            self.assertIn(f"mcp__{namespace}__get_current_user", allowed)

    def test_read_allowlist_matches_skill_mappings(self):
        reads = json.loads((self.root / "adapters/read-tools.json").read_text())
        self.assertEqual(reads["skills"], build_package.read_tools())
        self.assertTrue(all(reads["skills"].values()))
        self.assertEqual(reads["tools"], sorted({t for ts in reads["skills"].values() for t in ts}))
        self.assertTrue(all(not t.startswith(("create_", "update_", "delete_")) for t in reads["tools"]))

    def test_private_source_is_not_exported(self):
        (self.root / "CLAUDE.md").write_text("local agent configuration\n")
        (self.root / "docs/ben-practitioner-workbook.md").write_text("private source")
        files = export_release.release_files()
        self.assertNotIn("CLAUDE.md", files)
        self.assertNotIn("docs/ben-practitioner-workbook.md", files)

    def test_local_private_markers_are_enforced(self):
        (self.root / ".private-markers").write_text("# local\nExamplePerson\n")
        (self.root / "README.md").write_text("Interview notes from ExamplePerson")
        with self.assertRaisesRegex(ValueError, "Private/source"):
            export_release.release_files()

    def test_private_marker_in_allowed_file_fails(self):
        (self.root / "README.md").write_text("Private file: /Users/example/source.md")
        with self.assertRaisesRegex(ValueError, "Private/source"):
            export_release.release_files()

    def test_private_filename_in_allowed_tree_fails(self):
        (self.root / "skills/ben-practitioner-workbook.md").write_text("private answers")
        with self.assertRaisesRegex(ValueError, "Private/source"):
            export_release.release_files()

    def test_credential_marker_fails(self):
        (self.root / "README.md").write_text("-----BEGIN " + "PRIVATE KEY-----")
        with self.assertRaisesRegex(ValueError, "credential marker"):
            export_release.release_files()

    def test_stale_manifest_fails(self):
        (self.root / "plugin.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            export_release.release_files()

    def test_symlinked_directory_fails(self):
        (self.root / "skills/extra").symlink_to(self.root / "docs", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            export_release.release_files()

    def test_broken_symlink_fails(self):
        (self.root / "skills/broken").symlink_to(self.root / "nonexistent")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            export_release.release_files()

    def test_unexpected_file_type_fails(self):
        (self.root / "skills/extra.env").write_text("SAMPLE=value")
        with self.assertRaisesRegex(ValueError, "Unexpected release file type"):
            export_release.release_files()

    def test_export_is_reproducible_and_inventory_matches(self):
        first = export_release.export(self.output)
        self.assertEqual(first, export_release.export(self.output))
        second = export_release.export(self.output.parent / "other-output")
        self.assertEqual(first["sha256"], second["sha256"])
        with zipfile.ZipFile(first["archive"]) as archive:
            self.assertEqual(len(archive.namelist()), first["file_count"])

    def test_changed_existing_export_is_not_overwritten(self):
        result = export_release.export(self.output)
        readme = Path(result["directory"]) / "README.md"
        readme.write_text("user change")
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            export_release.export(self.output)
        self.assertEqual(readme.read_text(), "user change")

    def test_existing_export_symlink_fails(self):
        result = export_release.export(self.output)
        (Path(result["directory"]) / "extra").symlink_to(self.root / "docs", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            export_release.export(self.output)

    def test_model_prompt_does_not_contain_grading_rubric(self):
        cases = json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())
        for case in cases:
            prompt = build_evals.prompt_for(case)
            self.assertIn(case["prompt"], prompt)
            for criterion in case["must"] + case["must_not"] + [case["contrast_reason"]]:
                self.assertNotIn(criterion, prompt)

    def test_skill_load_grader_requires_canonical_instructions_not_alias_name(self):
        destination = self.root.parent / "eval-copy"
        count = build_evals.build(self.root, destination, ["oncall-provisional*"])
        self.assertEqual(count, 1)
        grader = next((destination / "evals").glob("*/graders/skill-loaded.md")).read_text()
        self.assertIn("type: llm", grader)
        self.assertIn("arm: with-only", grader)
        self.assertIn("focus: trace", grader)
        self.assertIn("skills/on-call/SKILL.md", grader)
        self.assertIn("not the alias name alone", grader)
        common_grader = next((destination / "evals").glob("*/graders/common-loaded.md")).read_text()
        self.assertIn("arm: with-only", common_grader)
        self.assertIn("focus: trace", common_grader)
        self.assertIn("A link or mention inside SKILL.md is not a read", common_grader)
        evidence_grader = next((destination / "evals").glob("*/graders/evidence-fidelity.md")).read_text()
        self.assertIn("focus: trace", evidence_grader)
        self.assertIn("Compare every factual assertion", evidence_grader)
        self.assertIn("Conditional potential risks", evidence_grader)
        self.assertIn("FAIL for a failed/denied call", grader)


if __name__ == "__main__":
    unittest.main()
