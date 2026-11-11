"""Offline checks only; these tests never connect to Rootly."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from capture_rootly_schema import summarize


class SchemaSummaryTests(unittest.TestCase):
    def page(self, tools):
        return [{"data": [{"name": "rootly", "authStatus": "oAuth", "tools": tools}]}]

    def test_missing_tool_is_not_claimed_available(self):
        result = summarize(self.page({"get_incident": {"annotations": {"readOnlyHint": True}}}),
                           ["get_incident", "list_communications_templates"])
        self.assertEqual(result["missing_tools"], ["list_communications_templates"])
        self.assertEqual(result["advertised_count"], 1)
        self.assertEqual(result["tool_calls"], 0)

    def test_annotations_are_not_assumed(self):
        result = summarize(self.page({"get_incident": {}, "update_incident": {}}), ["get_incident"])
        self.assertEqual(result["unexpected_tools"], ["update_incident"])
        self.assertEqual(result["unverified_read_only"], ["get_incident", "update_incident"])

    def test_wrong_or_missing_server_fails(self):
        with self.assertRaises(ValueError):
            summarize([{"data": []}], ["get_incident"])
        page = self.page({})
        page[0]["data"][0]["name"] = "unrelated"
        with self.assertRaises(ValueError):
            summarize(page, ["get_incident"])
