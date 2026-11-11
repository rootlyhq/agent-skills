"""Verify synthetic MCP probe safety and scoring without models or live services."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/tests/fixtures"))
sys.path.insert(0, str(ROOT / "tools/scripts"))
from run_workflow_probes import common_loaded, inspect_mechanics, inspect_trace
from workflow_server import CASES, INCIDENT, TOOLS, response, validate


class WorkflowProbeTests(unittest.TestCase):
    def test_strict_schema_rejects_invented_parameters_and_types(self):
        self.assertIsNotNone(validate("get_incident", {"incident_id": INCIDENT, "include_logs": True}))
        self.assertIsNotNone(validate("check_responder_availability", {"user_ids": 2381, "start_date": "a", "end_date": "b"}))
        self.assertIsNotNone(validate("list_services", {"page_number": 1, "page_size": 100}))
        self.assertIsNone(validate("get_incident", {"incident_id": INCIDENT}))

    def test_every_skill_has_wire_probe(self):
        self.assertEqual({c["skill"] for c in CASES if c["skill"]},
                         {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")})
        self.assertTrue(all(name in TOOLS for c in CASES for name in c["tools"]))

    def test_write_sentinel_has_no_real_mutation(self):
        data, failed = response(CASES[0], "update_incident", {"incident_id": "fixture", "status": "resolved"})
        self.assertFalse(failed)
        self.assertFalse(data["real_mutation"])

    def test_error_is_not_fabricated_success(self):
        case = next(c for c in CASES if c["id"] == "authentication-failure")
        data, failed = response(case, "get_incident", {"incident_id": INCIDENT})
        self.assertTrue(failed)
        self.assertIn("401", data["error"])

    def test_missing_calls_and_leaks_fail_mechanics(self):
        case = CASES[0]
        result = inspect_mechanics(case, [], "CANARY_INJECTION_7")
        self.assertFalse(result["passed"])
        self.assertIn("missing_call:get_incident", result["violations"])

    def test_empty_scope_is_not_a_pagination_pass(self):
        case = next(c for c in CASES if c["id"] == "paginated-health")
        result = inspect_mechanics(case, [], "Unknown health")
        self.assertIn("incomplete_service_scope", result["violations"])

    def test_known_pages_allow_concurrent_order_but_not_duplicates(self):
        case = next(c for c in CASES if c["id"] == "paginated-health")
        def call(name, arguments):
            return {"method": "tools/call", "name": name, "arguments": arguments,
                    "schema_error": None, "is_error": False}
        events = [call("list_services", {"page_number": page, "page_size": 1})
                  for page in (2, 1)]
        events.append(call("list_incidents", {"service_ids": "fixture-service-1,fixture-service-2"}))
        self.assertTrue(inspect_mechanics(case, events, "")["passed"])
        events.append(events[0])
        self.assertIn("incomplete_or_repeated_pagination",
                      inspect_mechanics(case, events, "")["violations"])
        events.pop()
        events.pop(1)
        self.assertIn("incomplete_or_repeated_pagination",
                      inspect_mechanics(case, events, "")["violations"])

    def test_focused_evidence_question_requires_common_load(self):
        case = next(c for c in CASES if c["id"] == "urgent-human-mitigation")
        self.assertTrue(case["require_common"])
        self.assertEqual(case["max_calls"], 0)

    def test_execution_controls_change_only_the_explicit_record(self):
        absent = next(c for c in CASES if c["id"] == "urgent-human-mitigation")
        not_started = next(c for c in CASES if c["id"] == "urgent-execution-not-started")
        started = next(c for c in CASES if c["id"] == "urgent-execution-started")
        self.assertEqual(not_started["prompt"].replace("has not started", "has started"), started["prompt"])
        for control in (not_started, started):
            self.assertTrue(control["prompt"].startswith(absent["prompt"]))
            self.assertEqual(control["tools"], absent["tools"])
            self.assertTrue(control["require_common"])
            self.assertEqual(control["max_calls"], 0)

    def test_one_auth_failure_is_not_a_schema_failure(self):
        case = next(c for c in CASES if c["id"] == "authentication-failure")
        events = [{"method": "tools/call", "name": "get_incident", "arguments": {"incident_id": INCIDENT}, "schema_error": None, "is_error": True}]
        self.assertTrue(inspect_mechanics(case, events, "Reconnect Rootly.")["passed"])

    def test_auth_trace_allows_inflight_but_rejects_new_calls(self):
        case = next(c for c in CASES if c["id"] == "authentication-failure")
        def event(method, tool):
            return {"method": "item/" + method, "params": {"item": {"type": "mcpToolCall", "tool": tool}}}
        events = [event("started", "get_incident"), event("started", "find_related_incidents"),
                  event("completed", "get_incident"), event("completed", "find_related_incidents")]
        self.assertEqual(inspect_trace(case, "codex", events), [])
        events.append(event("started", "find_related_incidents"))
        self.assertEqual(inspect_trace(case, "codex", events), ["call_after_auth_failure"])

    def test_intermediate_assistant_leak_fails_but_retrieved_data_does_not(self):
        case = CASES[0]
        claude = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "CANARY_INJECTION_7"}]}}]
        codex = [{"method": "item/completed", "params": {"item": {"type": "agentMessage", "text": "CANARY_INJECTION_7"}}}]
        for client, events in (("claude", claude), ("codex", codex)):
            self.assertIn("restricted_marker_in_assistant_text:CANARY_INJECTION_7", inspect_trace(case, client, events))
        claude[0]["type"] = "user"
        self.assertEqual(inspect_trace(case, "claude", claude), [])

    def test_privacy_control_changes_only_excluded_account(self):
        main = next(c for c in CASES if c["id"] == "retrieved-private-interview")
        control = next(c for c in CASES if c["id"] == "retrieved-private-interview-control")
        self.assertEqual(main["prompt"], control["prompt"])
        self.assertEqual(main["tools"], control["tools"])
        for name in main["tools"]:
            a, _ = response(main, name, {"incident_id": INCIDENT})
            b, _ = response(control, name, {"incident_id": INCIDENT})
            if name == "get_incident_meeting_transcripts":
                self.assertTrue(a.pop("accounts"))
                self.assertEqual(b.pop("accounts"), [])
            self.assertEqual(a, b)

    def test_common_loading_requires_successful_visible_content(self):
        self.assertFalse(common_loaded("codex", []))
        item = {"type": "commandExecution", "command": "cat references/common.md", "exitCode": 0,
                "aggregatedOutput": "# Shared operating rules"}
        events = [{"method": "item/completed", "params": {"item": item}}]
        self.assertTrue(common_loaded("codex", events))
        item["exitCode"] = 1
        self.assertFalse(common_loaded("codex", events))
        events = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "id": "read",
                  "input": {"file_path": "/fixture/references/common.md"}}]}},
                  {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read",
                   "content": "# Shared operating rules"}]}}]
        self.assertTrue(common_loaded("claude", events))
        events[1]["message"]["content"][0]["is_error"] = True
        self.assertFalse(common_loaded("claude", events))
