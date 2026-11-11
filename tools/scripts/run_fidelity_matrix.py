#!/usr/bin/env python3
"""Run the evidence-fidelity cases across Claude models and Codex.

Mitigation cases reuse tools/scripts/run_workflow_probes.py (synthetic MCP fixture,
explicit skill invocation). Deploy cases use supplied facts with no MCP server.
Every run lands in <output>/<client>-<model>/<client>-<case>-run-NN/ with
result.json and final.md, ready for tools/scripts/fidelity_gate.py. Failures are kept.
"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import fidelity_matrix
import run_codex_evals
import run_workflow_probes
from build_evals import prompt_for
from run_workflow_probes import common_loaded

ROOT = Path(__file__).resolve().parents[2]
MITIGATION = ["urgent-human-mitigation", "urgent-execution-not-started", "urgent-execution-started"]


def deploy_case(case_id):
    return next(c for c in json.loads((ROOT / "tools/tests/behavior/cases.json").read_text()) if c["id"] == case_id)


def claude_prompt(case):
    """The exact text sent to Claude, retained beside each result for later review."""
    return "Use /rootly:" + case["skill"] + " for this request.\n" + prompt_for(case)


def claude_facts(package, case, folder, model):
    """Supplied-facts Claude run with the same isolation as the probe runner, minus MCP."""
    prompt = claude_prompt(case)
    settings = json.loads((ROOT / "adapters/claude/readonly.settings.json").read_text())
    command = ["claude", "-p", prompt, "--no-session-persistence", "--setting-sources", "",
               "--restricted", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
               "--settings", json.dumps(settings), "--permission-mode", "dontAsk",
               "--tools", "Read,Glob,Grep,Skill", "--plugin-dir", str(package), "--add-dir", str(package),
               "--output-format", "stream-json", "--verbose", "--model", model]
    with tempfile.TemporaryDirectory(prefix="rootly-fidelity-") as workspace, \
            (folder / "trace.jsonl").open("x") as stdout, (folder / "stderr").open("x") as stderr:
        process = subprocess.run(command, cwd=workspace, stdout=stdout, stderr=stderr,
                                 stdin=subprocess.DEVNULL, timeout=300)
    events = [json.loads(line) for line in (folder / "trace.jsonl").read_text().splitlines() if line.startswith("{")]
    finals = [e for e in events if e.get("type") == "result"]
    if process.returncode or not finals or finals[-1].get("is_error"):
        raise RuntimeError("Claude did not complete; inspect private trace")
    models = sorted({e["message"]["model"] for e in events if e.get("type") == "assistant"
                     and e.get("message", {}).get("model")})
    if len(models) != 1:
        raise RuntimeError(f"Expected one assistant model, saw {models}")
    visible = [block["text"] for e in events if e.get("type") == "assistant"
               for block in e.get("message", {}).get("content", [])
               if isinstance(block, dict) and block.get("type") == "text"]
    (folder / "visible.md").write_text("\n\n".join(visible + [finals[-1].get("result", "")]))
    return finals[-1].get("result", ""), models[0], common_loaded("claude", events)


def run_deploy(client, case_id, package, output, repeat, model):
    case = deploy_case(case_id)
    folder = output / f"{client}-{case_id}-run-{repeat:02d}"
    folder.mkdir()
    # Retain the prompt itself, not only its hash: a later review cannot
    # reconstruct an invocation prefix from a digest.
    sent = claude_prompt(case) if client == "claude" else prompt_for(case)
    (folder / "prompt.txt").write_text(sent)
    result = {"client": client, "case": case_id, "repeat": repeat, "status": "error",
              "requested_model": model if client == "claude" else None,
              "codex_model_override": os.environ.get("ROOTLY_EVAL_CODEX_MODEL") if client == "codex" else None,
              "package_inventory_sha256": hashlib.sha256((package / "release-inventory.json").read_bytes()).hexdigest(),
              # The case body, and separately the text actually sent.
              "prompt_sha256": hashlib.sha256(prompt_for(case).encode()).hexdigest(),
              "sent_prompt_sha256": hashlib.sha256(sent.encode()).hexdigest()}
    started = time.monotonic()
    try:
        if client == "claude":
            answer, actual, common = claude_facts(package, case, folder, model)
            result.update(model=actual, model_identity_source="assistant_message", common_loaded=common)
        else:
            codex = run_codex_evals.run(case, package, folder, True)
            if codex["status"] != "completed":
                raise RuntimeError(codex.get("error", "Codex run did not complete"))
            answer = (folder / f"{case_id}-with.md").read_text()
            (folder / "visible.md").write_text((folder / f"{case_id}-with-visible.md").read_text())
            result.update(model=codex.get("model"), model_identity_source="thread_start",
                          common_loaded=codex.get("common_loaded"))
        (folder / "final.md").write_text(answer.rstrip("\n") + "\n")
        result["status"] = "completed"
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    result["duration_seconds"] = round(time.monotonic() - started, 2)
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def run_mitigation(client, case_id, package, output, repeat, model):
    case = next(c for c in run_workflow_probes.CASES if c["id"] == case_id)
    return run_workflow_probes.run(client, case, package, output, repeat, model if client == "claude" else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--claude-model", choices=("fable", "opus", "sonnet"), action="append", default=[])
    parser.add_argument("--codex", action="store_true", help="Also run Codex")
    parser.add_argument("--codex-model", help="Override the Codex model for this run only")
    parser.add_argument("--runs", type=int, choices=range(1, 11), default=3)
    parser.add_argument("--case", choices=fidelity_matrix.CASES, action="append", help="Override cases; release clearance requires exactly the release cases")
    parser.add_argument("--jobs", type=int, choices=range(1, 9), default=3)
    args = parser.parse_args()
    if args.codex_model:
        if not args.codex:
            parser.error("--codex-model requires --codex")
        os.environ["ROOTLY_EVAL_CODEX_MODEL"] = args.codex_model
    package = args.package.resolve()
    output = args.output.resolve()
    cases = args.case or list(fidelity_matrix.RELEASE_CASES)
    arms = [("claude", m) for m in args.claude_model] + ([("codex", "default")] if args.codex else [])
    if not arms:
        raise SystemExit("Choose at least one --claude-model or --codex")
    manifest = fidelity_matrix.manifest(package, [f"{c}-{m}" for c, m in arms], cases, args.runs)
    output.mkdir(parents=True, exist_ok=False)
    (output / "matrix-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    selection = {"codex_model_override": os.environ.get("ROOTLY_EVAL_CODEX_MODEL") if args.codex else None}
    (output / "model-selection.json").write_text(json.dumps(selection, indent=2) + "\n")
    jobs = []
    for client, model in arms:
        arm_dir = output / f"{client}-{model}"
        arm_dir.mkdir()
        for case_id in cases:
            runner = run_mitigation if case_id in MITIGATION else run_deploy
            for repeat in range(1, args.runs + 1):
                jobs.append((runner, client, case_id, arm_dir, repeat, model))
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(runner, client, case_id, package, arm_dir, repeat, model)
                   for runner, client, case_id, arm_dir, repeat, model in jobs]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            (output / "runs.json").write_text(json.dumps(results, indent=2) + "\n")
            print(json.dumps({k: result.get(k) for k in ("client", "case", "repeat", "model", "status", "error")}), flush=True)
    raise SystemExit(0 if all(r["status"] == "completed" for r in results) else 1)


if __name__ == "__main__":
    main()
