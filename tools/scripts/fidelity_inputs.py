"""Reconstruct matrix prompts and fingerprint their local execution inputs."""

import hashlib
import json
from pathlib import Path

from build_evals import prompt_for

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "tools/tests/behavior/cases.json",
    "tools/tests/fixtures/workflow_server.py",
    "tools/scripts/fidelity_inputs.py",
    "tools/scripts/run_fidelity_matrix.py",
    "tools/scripts/run_workflow_probes.py",
    "tools/scripts/run_codex_evals.py",
    "tools/scripts/codex_client.py",
    "tools/scripts/build_evals.py",
)


def sha(content):
    return hashlib.sha256(content).hexdigest()


def source_hashes():
    return {name: sha((ROOT / name).read_bytes()) for name in SOURCES}


def expected_prompt(case_id, client):
    """Return the case body, sent text and source fixture digest for one arm."""
    cases = json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())
    case = next((case for case in cases if case["id"] == case_id), None)
    if case is None:
        # The native probe runner loads this same fixture module.
        import run_workflow_probes
        case = next(case for case in run_workflow_probes.CASES if case["id"] == case_id)
        prompt = case["prompt"]
        source = ROOT / "tools/tests/fixtures/workflow_server.py"
    else:
        prompt = prompt_for(case)
        source = ROOT / "tools/tests/behavior/cases.json"
    prefix = f"Use /rootly:{case['skill']} for this request.\n" if client == "claude" and case["skill"] else ""
    return {"prompt_sha256": sha(prompt.encode()), "sent_prompt_sha256": sha((prefix + prompt).encode()),
            "fixture_sha256": sha(source.read_bytes())}, prefix + prompt
