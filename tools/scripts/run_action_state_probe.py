#!/usr/bin/env python3
"""Native-client prototype of a host-owned structured-output gate.

Synthetic snapshots only; no MCP servers, live writes, hooks, or model-authored
evidence. Raw output stays in private traces. Only validated fields are rendered.
Requires the specified package installed in Codex for Codex tests.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from action_state_guard import candidate_schema, digest, evaluate, model_evidence, parse_json
from codex_client import Client
from run_workflow_probes import common_loaded

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/tests/fixtures"))
from action_state_cases import CASES


def prompt_for(case):
    return ("Use the incident-response skill and read its common rules. This is a synthetic, "
            "read-only exercise; no MCP calls or actions. Return only the structured action-state "
            "candidate required by the output schema, not an incident assessment or free-text answer. "
            "Approval and execution are separate. Cite usable fact IDs for each reported state. "
            "If there is no usable evidence or usable reports conflict, state unknown with empty "
            "evidence_ids. Do not use approval as evidence of execution or nonexecution. The host "
            "will check the candidate against its own snapshot and render an attributed excerpt; "
            "it does not verify recovery, cause, safety, or whether to act.\n\nRequest:\n" + case["request"]
            + "\n\nHost-curated snapshot:\n" + json.dumps(model_evidence(case["evidence"]), indent=2))


def claude_result(events):
    finals = [e for e in events if e.get("type") == "result"]
    if len(finals) != 1 or finals[0].get("is_error") or not isinstance(finals[0].get("structured_output"), dict):
        raise ValueError("No single successful Claude structured result")
    models = sorted({e["message"]["model"] for e in events if e.get("type") == "assistant"
                     and e.get("message", {}).get("model")})
    if len(models) != 1:
        raise ValueError("Actual assistant model identity missing or ambiguous")
    return finals[0]["structured_output"], models[0]


def codex_result(events):
    # Never merge commentary into a final answer or extract JSON from prose.
    finals = [e["params"]["item"]["text"] for e in events if e.get("method") == "item/completed"
              and e.get("params", {}).get("item", {}).get("type") == "agentMessage"
              and e["params"]["item"].get("phase") == "final_answer"]
    if len(finals) != 1:
        raise ValueError("No single Codex final_answer item")
    return parse_json(finals[0])


def run_claude(package, workspace, folder, prompt, model):
    settings = {"permissions": {"allow": ["Read", "Glob", "Grep", "Skill"]}}
    command = ["claude", "-p", "Use /rootly:incident-response.\n" + prompt,
               "--model", model, "--restricted", "--setting-sources", "",
               "--no-session-persistence", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
               "--settings", json.dumps(settings), "--permission-mode", "dontAsk",
               "--tools", "Read,Glob,Grep,Skill", "--plugin-dir", str(package), "--add-dir", str(package),
               "--json-schema", json.dumps(candidate_schema()), "--output-format", "stream-json", "--verbose"]
    with (folder / "trace.jsonl").open("x") as trace, (folder / "stderr").open("x") as stderr:
        completed = subprocess.run(command, cwd=workspace, stdout=trace, stderr=stderr, timeout=180)
    if completed.returncode:
        raise RuntimeError("Claude did not complete successfully")
    events = [parse_json(line) for line in (folder / "trace.jsonl").read_text().splitlines() if line.startswith("{")]
    candidate, actual = claude_result(events)
    return candidate, actual, common_loaded("claude", events)


def run_codex(package, workspace, folder, prompt):
    with (folder / "trace.jsonl").open("x") as trace:
        client = Client(package, workspace, True, trace)
        try:
            catalog = client.request("skills/list", {"cwds": [str(workspace)], "forceReload": True})
            matches = [s for row in catalog["data"] for s in row["skills"]
                       if s["name"] == "rootly:incident-response" and s["enabled"]]
            if len(matches) != 1:
                raise RuntimeError("Expected one installed incident-response skill")
            skill = matches[0]
            inventory = parse_json((package / "release-inventory.json").read_text())
            for relative, expected_hash in inventory.items():
                prefix = "skills/incident-response/"
                if relative.startswith(prefix):
                    path = Path(skill["path"]).parent / relative[len(prefix):]
                    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                        raise RuntimeError("Installed skill differs from requested package")
            thread = client.request("thread/start", {"cwd": str(workspace), "sandbox": "read-only",
                                                       "approvalPolicy": "never", "ephemeral": True})
            turn = client.request("turn/start", {"threadId": thread["thread"]["id"], "outputSchema": candidate_schema(),
                "input": [{"type": "text", "text": "$rootly:incident-response\n" + prompt},
                          {"type": "skill", "name": skill["name"], "path": skill["path"]}]})
            events = []
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                event = client.receive_turn(thread["thread"]["id"], turn["turn"]["id"], max(.01, deadline - time.monotonic()))
                events.append(event)
                if event.get("method") == "turn/completed":
                    if event["params"]["turn"]["status"] != "completed":
                        raise RuntimeError("Codex turn did not complete successfully")
                    return codex_result(events), thread["model"], common_loaded("codex", events)
            raise TimeoutError("Codex turn deadline")
        finally:
            client.close()


def run(client, case, package, output, claude_model):
    folder = output / (client + "-" + case["id"])
    result = {"client": client, "case": case["id"], "status": "error", "accepted": False,
              "display": "Action-state excerpt withheld: validation did not complete."}
    created = False
    try:
        folder.mkdir()
        created = True
        prompt = prompt_for(case)
        # Snapshot these inputs before calling the model. Never accept its evidence.
        evidence = parse_json(json.dumps(case["evidence"]))
        (folder / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        (folder / "prompt.md").write_text(prompt)
        result.update(evidence_sha256=digest(evidence), prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                      schema_sha256=digest(candidate_schema()),
                      guard_sha256=hashlib.sha256((ROOT / "tools/scripts/action_state_guard.py").read_bytes()).hexdigest())
        result["package_inventory_sha256"] = hashlib.sha256((package / "release-inventory.json").read_bytes()).hexdigest()
        result["client_version"] = subprocess.check_output([client, "--version"], text=True).strip()
        with tempfile.TemporaryDirectory(prefix="rootly-state-probe-") as temporary:
            workspace = Path(temporary)
            if client == "claude":
                item, model, loaded = run_claude(package, workspace, folder, prompt, claude_model)
            else:
                item, model, loaded = run_codex(package, workspace, folder, prompt)
        (folder / "candidate.json").write_text(json.dumps(item, indent=2) + "\n")
        verdict = evaluate(evidence, item)
        (folder / "validation.json").write_text(json.dumps(verdict, indent=2) + "\n")
        result.update(status="completed", model=model,
                      model_identity_source="assistant_message" if client == "claude" else "thread_start",
                      common_loaded=loaded,
                      candidate_sha256=digest(item), accepted=verdict["accepted"], errors=verdict["errors"])
        result["display"] = verdict["rendered"] if verdict["accepted"] else "Action-state excerpt withheld: candidate failed evidence validation."
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    if created:
        try:
            (folder / "display.md").write_text(result["display"] + "\n")
            (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        except OSError:
            # A partial/missing audit is not a successful delivery. The aggregate
            # can still retain this error when the per-case destination fails.
            result.update(status="error", accepted=False, error="artifact_write_failed",
                          display="Action-state excerpt withheld: audit recording failed.")
    return result


def select_cases(requested):
    if requested and set(requested) - {c["id"] for c in CASES}:
        raise ValueError("Unknown case ID; no cases started")
    return [c for c in CASES if not requested or c["id"] in requested]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--client", choices=("both", "claude", "codex"), default="both")
    parser.add_argument("--case", action="append")
    parser.add_argument("--claude-model", default="fable")
    args = parser.parse_args()
    try:
        cases = select_cases(args.case)
    except ValueError as error:
        parser.error(str(error))
    args.output.mkdir(parents=True, exist_ok=False)
    clients = ("claude", "codex") if args.client == "both" else (args.client,)
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, client, case, args.package.resolve(), args.output.resolve(), args.claude_model)
                   for case in cases for client in clients]
        for future in as_completed(futures):
            item = future.result()
            results.append(item)
            (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
            print(json.dumps({key: item.get(key) for key in ("client", "case", "status", "accepted", "common_loaded")}), flush=True)
    # A correct rejection is a gate success but not a usable answer. Keep these
    # separate; this exit code reports only completed, skill-loaded client turns.
    return 0 if all(r["status"] == "completed" and r["common_loaded"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
