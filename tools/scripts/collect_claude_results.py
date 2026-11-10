#!/usr/bin/env python3
"""Preserve native Claude eval traces and final responses from a completed report."""

import argparse
import json
import shutil
from pathlib import Path

from run_workflow_probes import common_loaded


def collect(report, output):
    data = json.loads(report.read_text())
    output.mkdir(parents=True, exist_ok=False)
    summary = []
    for case in data["cases"]:
        for arm, runs in case["arms"].items():
            for index, run in enumerate(runs):
                name = f"{case['name']}-{arm}-{index}"
                source = Path(run["tracePath"])
                shutil.copyfile(source, output / (name + ".jsonl"))
                events = [json.loads(line) for line in source.read_text().splitlines() if line.startswith("{")]
                result = next((e for e in reversed(events) if e.get("type") == "result"), {})
                final = result.get("result", "")
                models = sorted({e["message"]["model"] for e in events if e.get("type") == "assistant"
                                 and e.get("message", {}).get("model")})
                init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
                (output / (name + ".md")).write_text(final + "\n")
                summary.append({"case": case["name"], "arm": arm, "run": index,
                                "message_models": models, "initialization_model": init.get("model"),
                                "client_version": init.get("claude_code_version"),
                                "automatic_pass": run["passed"], "error": run.get("error"),
                                "common_loaded": common_loaded("claude", events),
                                "failed_graders": [g["name"] for g in run["graders"] if not g["passed"]]})
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Preserved {len(summary)} native results; automatic grades require review")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    collect(args.report, args.output)
