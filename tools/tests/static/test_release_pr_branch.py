import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import release_pr_branch


class ReleaseBranchTests(unittest.TestCase):
    def test_unchanged_release_has_no_branch_and_does_not_parse_absent_json(self):
        for created in ("", "false"):
            self.assertEqual(release_pr_branch.select(created, ""), "")

    def test_created_release_selects_its_branch(self):
        payload = json.dumps([{"headBranchName": "release-please--branches--main"}])
        self.assertEqual(release_pr_branch.select("true", payload), "release-please--branches--main")

    def test_claimed_creation_requires_one_valid_branch(self):
        for payload in ("", "[]", "{}", "[{}]", '[{},{}]',
                        '[{"headBranchName":"main"}]',
                        '[{"headBranchName":"release-please--main\\nother=value"}]'):
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                release_pr_branch.select("true", payload)

    def test_cli_writes_a_safe_empty_output_for_the_observed_no_change_case(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            env = {**os.environ, "PRS_CREATED": "false", "RELEASE_PRS": "", "GITHUB_OUTPUT": str(output)}
            subprocess.run([sys.executable, str(ROOT / "tools/scripts/release_pr_branch.py")],
                           env=env, check=True)
            self.assertEqual(output.read_text(), "branch=\n")

    def test_workflow_reads_outputs_after_checkout_and_never_evaluates_empty_json(self):
        workflow = yaml.load((ROOT / ".github/workflows/release-please.yml").read_text(), Loader=yaml.BaseLoader)
        steps = workflow["jobs"]["release-pr"]["steps"]
        selector = next(i for i, step in enumerate(steps) if step.get("id") == "pr")
        self.assertTrue(any(step.get("uses", "").startswith("actions/checkout@") and "if" not in step
                            for step in steps[:selector]))
        self.assertTrue(any(step.get("uses", "").startswith("actions/setup-python@") and "if" not in step
                            for step in steps[:selector]))
        self.assertNotIn("fromJSON", json.dumps(steps))
        sync = next(step for step in steps if step.get("name") == "Synchronize derived metadata")
        dispatch = next(step for step in steps if step.get("name") == "Validate the release PR head")
        self.assertEqual(sync["if"], "steps.pr.outputs.branch != ''")
        self.assertEqual(dispatch["if"], "steps.pr.outputs.branch != ''")
        self.assertEqual(dispatch["env"]["RELEASE_BRANCH"], "${{ steps.pr.outputs.branch }}")
