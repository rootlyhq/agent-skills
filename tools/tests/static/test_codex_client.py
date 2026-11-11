"""Check invocation semantics and fail-closed live opt-in without calling a client."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
from codex_client import Client, answer_text
from run_codex_evals import inputs_for


class CodexClientTests(unittest.TestCase):
    def test_final_format_is_separate_but_commentary_remains_visible(self):
        final, visible = answer_text([
            {"phase": "commentary", "text": "Unsupported production claim."},
            {"phase": "final_answer", "text": "The final answer."}])
        self.assertEqual(final, "The final answer.")
        self.assertIn("Unsupported production claim.", visible)
        self.assertIn(final, visible)

    def test_missing_or_ambiguous_final_phase_is_rejected(self):
        for items in ([], [{"text": "missing phase"}], [{"phase": "commentary", "text": "progress"}],
                      [{"phase": "final_answer", "text": "one"}, {"phase": "final_answer", "text": "two"}]):
            with self.subTest(items=items), self.assertRaises(ValueError):
                answer_text(items)

    def test_receive_turn_ignores_foreign_completion_and_requires_both_ids(self):
        client = object.__new__(Client)
        child = {"method": "turn/completed", "params": {"threadId": "child", "turn": {"id": "t"}}}
        other_turn = {"method": "turn/completed", "params": {"threadId": "root", "turn": {"id": "old"}}}
        missing = {"method": "turn/completed", "params": {"turn": {"id": "t"}}}
        final = {"method": "item/completed", "params": {"threadId": "root", "turnId": "t",
                 "item": {"type": "agentMessage", "text": "Main answer"}}}
        done = {"method": "turn/completed", "params": {"threadId": "root", "turn": {"id": "t"}}}
        client.receive = Mock(side_effect=[child, other_turn, missing, final, done])
        self.assertEqual(client.receive_turn("root", "t", 1), final)
        self.assertEqual(client.receive_turn("root", "t", 1), done)
        with self.assertRaises(ValueError):
            client.receive_turn("root", "", 1)

    def test_receive_turn_rejects_unexpected_delegation(self):
        client = object.__new__(Client)
        client.receive = Mock(return_value={"method": "item/completed", "params": {
            "threadId": "root", "turnId": "t", "item": {"type": "subAgentActivity"}}})
        with self.assertRaisesRegex(RuntimeError, "Unexpected delegation"):
            client.receive_turn("root", "t", 1)

    def test_probe_launch_disables_delegation_without_global_config_edits(self):
        trace = SimpleNamespace(name="fixture-trace.jsonl")
        with patch("codex_client.subprocess.check_output", return_value="[]"), \
                patch("codex_client.open", mock_open()), \
                patch("codex_client.subprocess.Popen", side_effect=RuntimeError("stop before launch")) as launch:
            with self.assertRaisesRegex(RuntimeError, "stop before launch"):
                Client(ROOT, ROOT, True, trace)
        command = launch.call_args.args[0]
        self.assertIn("features.multi_agent=false", command)
        self.assertIn("agents.enabled=false", command)
        self.assertEqual(command[command.index("features.multi_agent=false") - 1], "-c")
        self.assertEqual(command[command.index("agents.enabled=false") - 1], "-c")

    def test_bundled_mode_restricts_the_plugin_server_under_its_full_unquoted_id(self):
        """A bare or quoted plugin key is silently ignored by Codex; the catalog then exposes every tool."""
        trace = SimpleNamespace(name="fixture-trace.jsonl")
        with patch("codex_client.subprocess.check_output", return_value="[]"), \
                patch("codex_client.open", mock_open()), \
                patch("codex_client.subprocess.Popen", side_effect=RuntimeError("stop before launch")) as launch:
            with self.assertRaisesRegex(RuntimeError, "stop before launch"):
                Client(ROOT, ROOT, True, trace, bundled_read_tools=["get_current_user"])
        settings = [arg for arg in launch.call_args.args[0] if arg.startswith("plugins.")]
        self.assertIn('plugins.rootly@rootly-agent-skills.mcp_servers.rootly.enabled_tools=["get_current_user"]', settings)
        self.assertFalse([arg for arg in settings if arg.startswith(("plugins.rootly.mcp", 'plugins."'))], settings)

    def test_bundled_mode_rejects_writes_and_mixed_sources_before_startup(self):
        with patch("codex_client.subprocess.check_output") as launch:
            for options in (
                {"bundled_read_tools": []},
                {"bundled_read_tools": ["update_incident"]},
                {"bundled_read_tools": ["get_current_user"], "rootly_read_tools": ["get_current_user"]},
                {"bundled_read_tools": ["get_current_user"], "fixture_server": {}},
            ):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    Client(ROOT, ROOT, True, None, **options)
            with self.assertRaises(ValueError):
                Client(ROOT, ROOT, False, None, bundled_read_tools=["get_current_user"])
            launch.assert_not_called()

    def test_bundled_mode_rejects_unrestricted_server_url(self):
        """Live probes must reject a package that drops the server read-only request."""
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as folder:
            package = Path(folder)
            (package / "adapters").mkdir()
            (package / "adapters/read-tools.json").write_text(
                json.dumps({"tools": ["get_current_user"]}))
            for manifest in (".mcp.json", "mcp.json"):
                with self.subTest(manifest=manifest):
                    for name in (".mcp.json", "mcp.json"):
                        content = json.loads((ROOT / name).read_text())
                        if name == manifest:
                            content["mcpServers"]["rootly"]["url"] = "https://mcp.rootly.com/mcp"
                        (package / name).write_text(json.dumps(content))
                    with patch("codex_client.subprocess.Popen") as launch:
                        with self.assertRaisesRegex(ValueError, "Unexpected .* server declaration"):
                            Client(package, package, True,
                                   SimpleNamespace(name="unused-trace.jsonl"),
                                   bundled_read_tools=["get_current_user"])
                    launch.assert_not_called()

    def test_default_prompt_is_text_not_an_explicit_skill_attachment(self):
        case = json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())[0]
        skill = {"name": "rootly:" + case["skill"], "path": "/skill/SKILL.md",
                 "interface": {"defaultPrompt": "Use $" + case["skill"] + " for this workflow."}}
        inputs = inputs_for(case, skill, "default-prompt")
        self.assertEqual(len(inputs), 1)
        self.assertTrue(inputs[0]["text"].startswith(skill["interface"]["defaultPrompt"] + "\n\n"))
        self.assertEqual(inputs_for(case, skill, "explicit")[1]["type"], "skill")
        self.assertEqual(len(inputs_for(case, skill, "implicit")), 1)
