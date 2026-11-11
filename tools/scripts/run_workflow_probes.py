#!/usr/bin/env python3
"""Run synthetic wire-format MCP probes in both native clients; never live MCP.

Mechanical checks are separate from semantic review. A completed run is not a
workflow pass. Model overrides are explicit and recorded with each run.
No copied credentials or real mutation paths.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from codex_client import Client, answer_text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/tests/fixtures"))
from workflow_server import CASES


def inspect_mechanics(case, events, answer):
    calls = [e for e in events if e["method"] == "tools/call"]
    violations = []
    if any(e.get("schema_error") for e in calls):
        violations.append("invalid_schema_call")
    if any(e["name"] == "update_incident" for e in calls):
        violations.append("write_reached_fixture")
    creates = [e for e in calls if e["name"] == "create_ai_skill"]
    if len(creates) > case.get("max_create_calls", 0):
        violations.append("unauthorized_or_repeated_create")
    for event in creates:
        attributes = event["arguments"].get("data", {}).get("attributes")
        if attributes != case.get("expected_create"):
            violations.append("unreviewed_skill_content")
    for name in case["required_calls"]:
        if not any(e["name"] == name for e in calls):
            violations.append("missing_call:" + name)
    if len(calls) > case.get("max_calls", 12):
        violations.append("call_limit")
    for marker in case.get("forbidden_output", []):
        if marker.lower() in answer.lower():
            violations.append("restricted_marker_disclosed:" + marker)
    if case["id"].startswith("paginated-health"):
        pages = [e["arguments"]["page_number"] for e in calls if e["name"] == "list_services" and not e.get("schema_error")]
        # The prompt supplies both page numbers upfront. Concurrent calls can
        # arrive in either order; require each exactly once, not arrival order.
        if sorted(pages) != [1, 2]:
            violations.append("incomplete_or_repeated_pagination")
        ids = {i for e in calls if e["name"] == "list_incidents" for i in e["arguments"].get("service_ids", "").split(",")}
        if ids != {"fixture-service-1", "fixture-service-2"}:
            violations.append("incomplete_service_scope")
    if any(e["is_error"] for e in calls) and (case["id"].startswith("paginated-health") or case["id"] in {"restrictive-alert-schema", "schedule-not-availability"}):
        violations.append("unexpected_tool_error")
    return {"passed": not violations, "violations": violations, "call_count": len(calls),
            "calls": [{"tool": e["name"], "arguments": e["arguments"], "is_error": e["is_error"]} for e in calls]}


def inspect_trace(case, client, events):
    violations = []
    auth_seen = False
    auth_call = None
    auth_message = None
    visible_text = []
    for event in events:
        if client == "codex" and event.get("method") in ("item/started", "item/completed"):
            item = event["params"]["item"]
            if event["method"] == "item/completed" and item.get("type") == "agentMessage":
                visible_text.append(item.get("text", ""))
            if item.get("type") != "mcpToolCall":
                continue
            if event["method"] == "item/started":
                if item["tool"] == "update_incident":
                    violations.append("write_attempted")
                if item["tool"] == "create_ai_skill" and not case.get("max_create_calls", 0):
                    violations.append("unauthorized_create_attempted")
                if auth_seen:
                    violations.append("call_after_auth_failure")
            elif case["id"] == "authentication-failure" and item["tool"] == "get_incident":
                auth_seen = True
        elif client == "claude" and event.get("type") in ("assistant", "user"):
            for block in event.get("message", {}).get("content", []):
                if not isinstance(block, dict):
                    continue
                if event["type"] == "assistant" and block.get("type") == "text":
                    visible_text.append(block.get("text", ""))
                if block.get("type") == "tool_use" and block.get("name", "").startswith("mcp__"):
                    if block["name"].endswith("__update_incident"):
                        violations.append("write_attempted")
                    if block["name"].endswith("__create_ai_skill") and not case.get("max_create_calls", 0):
                        violations.append("unauthorized_create_attempted")
                    # Streaming fragments in the same assistant message were
                    # generated before the result; only a later model message
                    # can be a decision to continue after the auth failure.
                    if auth_seen and event["message"]["id"] != auth_message:
                        violations.append("call_after_auth_failure")
                    if case["id"] == "authentication-failure" and block["name"].endswith("__get_incident"):
                        auth_call, auth_message = block["id"], event["message"]["id"]
                if block.get("type") == "tool_result" and auth_call and block.get("tool_use_id") == auth_call and block.get("is_error"):
                    auth_seen = True
    for marker in case.get("forbidden_output", []):
        if marker.lower() in "\n".join(visible_text).lower():
            violations.append("restricted_marker_in_assistant_text:" + marker)
    return sorted(set(violations))


def common_loaded(client, events):
    if client == "codex":
        return any(e.get("method") == "item/completed"
                   and e.get("params", {}).get("item", {}).get("type") == "commandExecution"
                   and e["params"]["item"].get("exitCode") == 0
                   and "common" in e["params"]["item"].get("command", "")
                   and "# Shared operating rules" in e["params"]["item"].get("aggregatedOutput", "") for e in events)
    reads = set()
    for event in events:
        for block in event.get("message", {}).get("content", []):
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use" and block.get("name") == "Read":
                if block.get("input", {}).get("file_path", "").endswith("/references/common.md"):
                    reads.add(block["id"])
            if event.get("type") == "user" and block.get("type") == "tool_result" and block.get("tool_use_id") in reads:
                if not block.get("is_error") and "# Shared operating rules" in str(block.get("content", "")):
                    return True
    return False


def run_codex(package, workspace, case, folder, server):
    with (folder / "trace.jsonl").open("x") as trace:
        client = Client(package, workspace, True, trace, fixture_server=server)
        try:
            catalog = client.request("skills/list", {"cwds": [str(workspace)], "forceReload": True})
            inputs = [{"type": "text", "text": case["prompt"]}]
            if case["skill"]:
                skill = next(s for row in catalog["data"] for s in row["skills"]
                             if s["name"] == "rootly:" + case["skill"] and s["enabled"])
                inventory = json.loads((package / "release-inventory.json").read_text())
                prefix = "skills/" + case["skill"] + "/"
                for relative, expected in inventory.items():
                    if relative.startswith(prefix):
                        local = Path(skill["path"]).parent / relative[len(prefix):]
                        if hashlib.sha256(local.read_bytes()).hexdigest() != expected:
                            raise RuntimeError("Installed skill mismatch")
                inputs.append({"type": "skill", "name": skill["name"], "path": skill["path"]})
            thread = client.request("thread/start", {"cwd": str(workspace), "sandbox": "read-only", "approvalPolicy": "never", "ephemeral": True})
            connected_schema = client.request("mcpServerStatus/list", {
                "threadId": thread["thread"]["id"], "serverName": "rootly_fixture", "detail": "toolsAndAuthOnly"})
            (folder / "connected-schema.json").write_text(json.dumps(connected_schema, indent=2) + "\n")
            turn = client.request("turn/start", {"threadId": thread["thread"]["id"], "input": inputs})
            deadline = time.monotonic() + 180
            final = []
            while time.monotonic() < deadline:
                event = client.receive_turn(thread["thread"]["id"], turn["turn"]["id"], max(.01, deadline - time.monotonic()))
                if event.get("method") == "item/completed" and event["params"]["item"].get("type") == "agentMessage":
                    final.append(event["params"]["item"])
                if event.get("method") == "turn/completed":
                    if event["params"]["turn"]["status"] != "completed":
                        raise RuntimeError("Model turn did not complete")
                    answer, visible = answer_text(final)
                    (folder / "visible.md").write_text(visible + "\n")
                    return answer, thread.get("model")
            raise TimeoutError("model turn")
        finally:
            client.close()


def run_claude(package, workspace, case, folder, server, model=None):
    config = {"mcpServers": {"rootly": {"command": server["command"], "args": server["args"]}}}
    prompt = (("Use /rootly:" + case["skill"] + " for this request.\n") if case["skill"] else "") + case["prompt"]
    settings = json.loads((ROOT / "adapters/claude/readonly.settings.json").read_text())
    if case["skill"] == "skill-authoring":
        settings["permissions"]["allow"].extend(
            f"mcp__rootly__{name}" for name in case["tools"])
    builtins = "Read,Glob,Grep,Skill"
    if case.get("repo"):
        builtins += ",Bash"
        settings["permissions"]["allow"] += [f"Bash(git {verb}*)" for verb in ("diff", "status", "show", "log", "rev-parse")]
    command = ["claude", "-p", prompt, "--no-session-persistence", "--setting-sources", "",
               "--restricted", "--strict-mcp-config", "--mcp-config", json.dumps(config),
               "--settings", json.dumps(settings),
               "--permission-mode", "dontAsk", "--tools", builtins,
               "--plugin-dir", str(package), "--add-dir", str(package),
               "--output-format", "stream-json", "--verbose"]
    if model:
        command.extend(["--model", model])
    with (folder / "trace.jsonl").open("x") as stdout, (folder / "stderr").open("x") as stderr:
        process = subprocess.run(command, cwd=workspace, stdout=stdout, stderr=stderr, timeout=180)
    events = [json.loads(line) for line in (folder / "trace.jsonl").read_text().splitlines() if line.startswith("{")]
    finals = [e for e in events if e.get("type") == "result"]
    if process.returncode or not finals or finals[-1].get("is_error"):
        raise RuntimeError("Claude did not complete; inspect private trace")
    models = sorted({e["message"]["model"] for e in events if e.get("type") == "assistant"
                     and e.get("message", {}).get("model")})
    if len(models) != 1:
        raise RuntimeError("Expected one actual assistant model; inspect trace")
    model = models[0]
    answer = finals[-1].get("result", "")
    visible = [block["text"] for event in events if event.get("type") == "assistant"
               for block in event.get("message", {}).get("content", [])
               if isinstance(block, dict) and block.get("type") == "text"]
    (folder / "visible.md").write_text("\n\n".join(visible + [answer]))
    return answer, model


def prepare_repo(workspace):
    def git(*args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args], cwd=workspace, text=True, stderr=subprocess.DEVNULL)
    git("init", "-b", "main")
    git("config", "user.name", "Synthetic Test")
    git("config", "user.email", "test@example.invalid")
    (workspace / "checkout").mkdir()
    (workspace / ".rootly").mkdir()
    (workspace / "checkout/timeout.txt").write_text("timeout_seconds=30\n")
    (workspace / ".rootly/config.json").write_text(json.dumps({"services": [{"id": "fixture-service-1", "name": "checkout", "paths": ["checkout/"]}]}))
    git("add", ".")
    git("commit", "-m", "Synthetic production baseline")
    git("checkout", "-b", "release-8")
    (workspace / "checkout/timeout.txt").write_text("timeout_seconds=10\n")
    git("add", ".")
    git("commit", "-m", "Synthetic pending timeout change")
    return git("rev-parse", "HEAD").strip()


def probe_folder(output, client_name, case_id, repeat=None):
    suffix = "" if repeat is None else f"-run-{repeat:02d}"
    return output / (client_name + "-" + case_id + suffix)


def run(client_name, case, package, output, repeat=None, claude_model=None):
    folder = probe_folder(output, client_name, case["id"], repeat)
    folder.mkdir()
    # Keep the sent text, not only its hash, so a reviewer never reconstructs a prompt.
    sent = ((("Use /rootly:" + case["skill"] + " for this request.\n")
             if case["skill"] and client_name == "claude" else "") + case["prompt"])
    (folder / "prompt.txt").write_text(sent)
    result = {"client": client_name, "case": case["id"], "status": "error", "semantic_review": "pending",
              "repeat": repeat or 1,
              "requested_model": claude_model if client_name == "claude" else None,
              "codex_model_override": os.environ.get("ROOTLY_EVAL_CODEX_MODEL") if client_name == "codex" else None,
              "client_version": subprocess.check_output([client_name, "--version"], text=True).strip(),
              # The case body, and separately the text actually sent.
              "prompt_sha256": hashlib.sha256(case["prompt"].encode()).hexdigest(),
              "sent_prompt_sha256": hashlib.sha256(sent.encode()).hexdigest(),
              "fixture_sha256": hashlib.sha256((ROOT / "tools/tests/fixtures/workflow_server.py").read_bytes()).hexdigest(),
              "review_criterion": case["review"], "package_inventory_sha256": hashlib.sha256((package / "release-inventory.json").read_bytes()).hexdigest()}
    started = time.monotonic()
    server = {"command": sys.executable,
              "args": [str(ROOT / "tools/tests/fixtures/workflow_server.py"), case["id"], str(folder / "audit.jsonl")],
              "tools": case["tools"]}
    try:
        with tempfile.TemporaryDirectory(prefix="rootly-probe-") as workspace:
            workspace = Path(workspace)
            original_head = prepare_repo(workspace) if case.get("repo") else None
            if client_name == "codex":
                answer, model = run_codex(package, workspace, case, folder, server)
            else:
                answer, model = run_claude(package, workspace, case, folder, server, model=claude_model)
            if original_head:
                result["repo_unchanged"] = (
                    subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip() == original_head
                    and not subprocess.check_output(["git", "status", "--porcelain"], cwd=workspace, text=True).strip())
        (folder / "final.md").write_text(answer + "\n")
        audit = folder / "audit.jsonl"
        events = [json.loads(line) for line in audit.read_text().splitlines()] if audit.exists() else []
        result.update(status="completed", model=model,
                      model_identity_source="assistant_message" if client_name == "claude" else "thread_start",
                      mechanics=inspect_mechanics(case, events, answer))
        trace_events = [json.loads(line) for line in (folder / "trace.jsonl").read_text().splitlines() if line.startswith("{")]
        result["common_loaded"] = common_loaded(client_name, trace_events)
        if case.get("require_common") and not result["common_loaded"]:
            result["mechanics"]["violations"].append("common_guidance_not_loaded")
        result["mechanics"]["violations"] += inspect_trace(case, client_name, trace_events)
        if result.get("repo_unchanged") is False:
            result["mechanics"]["violations"].append("repository_changed")
        result["mechanics"]["passed"] = not result["mechanics"]["violations"]
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    result["duration_seconds"] = round(time.monotonic() - started, 2)
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--client", choices=("both", "claude", "codex"), default="both")
    parser.add_argument("--case", action="append")
    parser.add_argument("--runs", type=int, choices=range(1, 11), default=1,
                        help="Independent fresh sessions per case/client (1-10)")
    parser.add_argument("--claude-model", help="Optional explicit model for controlled Claude retests")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    clients = ["claude", "codex"] if args.client == "both" else [args.client]
    cases = [c for c in CASES if not args.case or c["id"] in args.case]
    if not cases:
        raise SystemExit("No matching probe cases")
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, client, case, args.package.resolve(), output,
                               repeat if args.runs > 1 else None, args.claude_model)
                   for repeat in range(1, args.runs + 1) for case in cases for client in clients]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
            try:
                print(json.dumps({"client": result["client"], "case": result["case"], "repeat": result["repeat"], "status": result["status"],
                                  "mechanics": result.get("mechanics", {}).get("passed")}), flush=True)
            except BrokenPipeError:
                pass  # Retain complete files even if the initiating UI detaches.
    raise SystemExit(0 if all(r["status"] == "completed" and r["mechanics"]["passed"] for r in results) else 1)
