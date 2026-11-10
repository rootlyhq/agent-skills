#!/usr/bin/env python3
"""Run supplied-facts decision scenarios repeatedly on one client, with retained prompts.

This is the exploratory round runner for investigation/responder scenarios that
have no deploy or focused-decision table. It supplies the case facts in the
prompt, never the expected answer or grading criteria, and runs each case in a
fresh session with no MCP server. Completion and reference loading are recorded
per run; semantic grading is left to tools/scripts/fidelity_gate.py --round and manual
review. A completed run is not a pass.
"""

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fidelity_contract
from run_fidelity_matrix import deploy_case, run_deploy

ROOT = Path(__file__).resolve().parents[2]


def case_ids():
    return [case["id"] for case in json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())]


def tool_activity(folder):
    """Completed tool calls in the trace, with what each read actually returned."""
    trace = folder / "trace.jsonl"
    if not trace.exists():
        return []
    events = [json.loads(line) for line in trace.read_text().splitlines() if line.startswith("{")]
    calls = {}
    for event in events:
        for block in event.get("message", {}).get("content", []):
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use":
                calls[block["id"]] = {"name": block["name"], "input": block.get("input", {}),
                                      "result_seen": False}
            if event.get("type") == "user" and block.get("type") == "tool_result":
                call = calls.get(block.get("tool_use_id"))
                if call is not None:
                    content = str(block.get("content", ""))
                    call.update(result_seen=True, is_error=bool(block.get("is_error")),
                                evidence_check_returned="## Final evidence check" in content)
    return list(calls.values())


def one(case_id, package, output, runs, model):
    rows = []
    for repeat in range(1, runs + 1):
        result = run_deploy("claude", case_id, package, output, repeat, model)
        folder = output / f"claude-{case_id}-run-{repeat:02d}"
        calls = tool_activity(folder)
        result["tool_activity"] = calls
        result["evidence_check_loaded"] = any(
            call["name"] == "Read" and call["input"].get("file_path", "").endswith("/references/evidence.md")
            and call.get("evidence_check_returned") and not call.get("is_error") for call in calls)
        result["mcp_calls"] = sum(call["name"].startswith("mcp__") for call in calls)
        answer = folder / "final.md"
        result["format"] = fidelity_contract.detected_format(answer.read_text()) if answer.exists() else None
        result["semantic_review"] = "pending"
        (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({key: result.get(key) for key in
                          ("case", "repeat", "status", "model", "common_loaded",
                           "evidence_check_loaded", "mcp_calls", "format", "error")}), flush=True)
        rows.append(result)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--case", action="append", required=True, choices=case_ids(), metavar="CASE")
    parser.add_argument("--runs", type=int, choices=range(1, 11), default=3)
    parser.add_argument("--claude-model", default="opus", choices=("fable", "opus", "sonnet"))
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    args = parser.parse_args()
    package, output = args.package.resolve(), args.output.resolve()
    cases = list(dict.fromkeys(args.case))
    for case_id in cases:
        deploy_case(case_id)  # Fail before any model call on an unknown case.
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(json.dumps({
        "surface": "Claude Code CLI; not Claude Desktop or Codex",
        "client_version": subprocess.check_output(["claude", "--version"], text=True).strip(),
        "requested_model": args.claude_model, "runs_per_case": args.runs, "cases": cases,
        "package": str(package),
        "inventory_sha256": hashlib.sha256((package / "release-inventory.json").read_bytes()).hexdigest(),
        "cases_sha256": hashlib.sha256((ROOT / "tools/tests/behavior/cases.json").read_bytes()).hexdigest(),
        "grading_criteria_sent_to_model": False,
        "sequential_update_test": False,
        "release_clearance": False,
    }, indent=2) + "\n")
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows = [row for batch in pool.map(
            lambda case_id: one(case_id, package, output, args.runs, args.claude_model), cases)
            for row in batch]
    (output / "runs.json").write_text(json.dumps(rows, indent=2) + "\n")
    complete = all(row["status"] == "completed" and row.get("common_loaded")
                   and not row["mcp_calls"] for row in rows)
    raise SystemExit(0 if complete else 1)


if __name__ == "__main__":
    main()
