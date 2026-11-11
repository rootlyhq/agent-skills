"""A quiet audit is not sufficient proof of a permission boundary."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_permissions import inspect_result


class PermissionVerifierTests(unittest.TestCase):
    def test_claude_requires_actual_host_denial_and_successful_read(self):
        audit = [{"name": "get_current_user"}]
        events = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "read", "name": "mcp__rootly__get_current_user", "input": {}},
                {"type": "tool_use", "id": "write", "name": "mcp__rootly__update_incident"}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "read", "content": "fixture-user"}]}}
        ]
        self.assertFalse(inspect_result("claude", audit, events, 0)["passed"])
        denial = {"type": "system", "subtype": "permission_denied", "tool_name": "mcp__rootly__update_incident", "tool_use_id": "write"}
        self.assertTrue(inspect_result("claude", audit, events + [denial], 0)["passed"])
        self.assertFalse(inspect_result("claude", audit, [events[0], denial], 0)["passed"])
        self.assertFalse(inspect_result("claude", audit + [{"name": "update_incident"}], events + [denial], 0)["passed"])

    def test_codex_requires_unavailable_statement_not_voluntary_refusal(self):
        audit = [{"name": "get_current_user", "_meta": {"x-codex-turn-metadata": {"model": "fixture-model"}}}]
        read = {"type": "item.completed", "item": {"type": "mcp_tool_call", "tool": "get_current_user",
                "status": "completed", "result": {"content": "fixture-user"}}}
        def message(text):
            return {"type": "item.completed", "item": {"type": "agent_message", "text": text}}
        self.assertFalse(inspect_result("codex", audit, [read], 0)["passed"])
        self.assertFalse(inspect_result("codex", audit, [read, message("I choose not to call update_incident.")], 0)["passed"])
        result = inspect_result("codex", audit, [read, message("update_incident: unavailable; no call could be made.")], 0)
        self.assertTrue(result["passed"])
        self.assertEqual(result["model"], "fixture-model")
        self.assertFalse(inspect_result("codex", audit, [read, message("update_incident: unavailable")], 1)["passed"])
