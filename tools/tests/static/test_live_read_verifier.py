"""Offline verification of the bounded live-read test; no network calls."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_live_incident import verify_calls


class LiveReadVerifierTests(unittest.TestCase):
    def calls(self):
        return [
            {"server": "rootly", "tool": "list_incidents", "status": "completed",
             "arguments": {"page_size": 1, "page_number": 1, "sort": "-created_at"},
             "result": {"structuredContent": {"incidents": [{"incident_id": "fixture-id"}]}}},
            {"server": "rootly", "tool": "get_incident", "status": "completed",
             "arguments": {"incident_id": "fixture-id"},
             "result": {"content": [{"type": "text", "text": '{"data":{"id":"fixture-id"}}'}]}},
        ]

    def test_scoped_success_matches_returned_id(self):
        self.assertTrue(verify_calls(self.calls(), "completed"))

    def test_completion_alone_is_not_success(self):
        cases = []
        calls = self.calls()
        calls[0]["arguments"]["page_size"] = 100
        cases.append(calls)
        calls = self.calls()
        calls[1]["arguments"]["incident_id"] = "invented-id"
        cases.append(calls)
        calls = self.calls()
        calls[1]["result"]["isError"] = True
        cases.append(calls)
        cases.append(self.calls() + [copy.deepcopy(self.calls()[0])])
        for calls in cases:
            self.assertFalse(verify_calls(calls, "completed"))
        self.assertFalse(verify_calls(self.calls(), "failed"))
