"""Review completion and deadline evidence; no real model calls."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_claude_review


class ReviewRunnerTests(unittest.TestCase):
    def test_timeout_retains_identity_and_incomplete_status(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prompt = root / "prompt.md"
            prompt.write_text("Review the fixture")

            def timeout(command, **kwargs):
                kwargs["stdout"].write(json.dumps({"type": "system", "subtype": "init",
                    "model": "claude-fable-5-1", "tools": ["Read"], "mcp_servers": []}) + "\n")
                kwargs["stdout"].write('{"type":')
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])

            with patch.object(run_claude_review.subprocess, "check_output", return_value="fixture CLI"), \
                 patch.object(run_claude_review.subprocess, "run", side_effect=timeout), \
                 patch("builtins.print"):
                with self.assertRaisesRegex(RuntimeError, "did not complete"):
                    run_claude_review.review(prompt, root / "result", timeout=1)
            metadata = json.loads((root / "result/metadata.json").read_text())
            self.assertTrue(metadata["timed_out"])
            self.assertFalse(metadata["completed"])
            self.assertEqual(metadata["model"], "claude-fable-5-1")
            self.assertEqual((root / "result/review.md").read_text(), "\n")


if __name__ == "__main__":
    unittest.main()
