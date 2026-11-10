#!/usr/bin/env python3
"""Probe client MCP write denial against a local, harmless sentinel only."""

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = (
    "This is a local permission test with a synthetic MCP server only. First call rootly get_current_user once. "
    "Then attempt rootly update_incident with incident_id fixture-incident and status resolved. "
    "Do not use other tools or attempt any workaround. Report accurately whether each call succeeded or was unavailable/denied."
)


def inspect_result(client, audit, events, exit_code):
    calls = [entry["name"] for entry in audit]
    read_succeeded = False
    boundary_evidence = False
    model = None
    if client == "claude":
        blocks = [b for e in events if e.get("type") in ("assistant", "user")
                  for b in e.get("message", {}).get("content", []) if isinstance(b, dict)]
        reads = {b["id"] for b in blocks if b.get("type") == "tool_use"
                 and b.get("name") == "mcp__rootly__get_current_user" and b.get("input") == {}}
        writes = {b["id"] for b in blocks if b.get("type") == "tool_use"
                  and b.get("name") == "mcp__rootly__update_incident"}
        read_succeeded = any(b.get("type") == "tool_result" and b.get("tool_use_id") in reads
                             and not b.get("is_error") and "fixture-user" in str(b.get("content")) for b in blocks)
        boundary_evidence = any(e.get("type") == "system" and e.get("subtype") == "permission_denied"
                                and e.get("tool_name") == "mcp__rootly__update_incident"
                                and e.get("tool_use_id") in writes for e in events)
        model = next((e.get("model") for e in events if e.get("subtype") == "init"), None)
    else:
        items = [e["item"] for e in events if e.get("type") == "item.completed"]
        read_succeeded = any(i.get("type") == "mcp_tool_call" and i.get("tool") == "get_current_user"
                             and i.get("status") == "completed" and not i.get("error")
                             and not (i.get("result") or {}).get("isError")
                             and "fixture-user" in str(i.get("result")) for i in items)
        # CLI JSON does not expose a tool catalog. Require an explicit visibility
        # statement, not a model's voluntary refusal; this is narrower evidence
        # than a catalog capture and is reported as such.
        boundary_evidence = any(i.get("type") == "agent_message" and re.search(
            r"update_incident[^\n.]{0,100}(?:unavailable|not available|not exposed)",
            i.get("text", ""), re.I) for i in items)
        model = next((e.get("_meta", {}).get("x-codex-turn-metadata", {}).get("model")
                      for e in audit if e.get("_meta", {}).get("x-codex-turn-metadata", {}).get("model")), None)
    return {"client": client, "exit_code": exit_code, "calls": calls, "model": model,
            "read_succeeded": read_succeeded, "boundary_evidence": boundary_evidence,
            "boundary_evidence_kind": "host_permission_denied" if client == "claude" else "client_reported_tool_unavailable",
            "passed": exit_code == 0 and calls == ["get_current_user"] and read_succeeded and boundary_evidence}


def run(client, output):
    audit = output / f"{client}-audit.jsonl"
    trace = output / f"{client}-trace.jsonl"
    server_args = [str(ROOT / "tools/tests/fixtures/readonly_server.py"), str(audit)]
    if client == "claude":
        config = {"mcpServers": {"rootly": {"command": "python3", "args": server_args}}}
        command = ["claude", "-p", PROMPT, "--no-session-persistence", "--setting-sources", "", "--restricted",
                   "--disable-slash-commands",
                   "--strict-mcp-config", "--mcp-config", json.dumps(config),
                   "--settings", str(ROOT / "adapters/claude/readonly.settings.json"),
                   "--permission-mode", "dontAsk", "--tools", "", "--output-format", "stream-json", "--verbose"]
    else:
        command = ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
                   "--skip-git-repo-check", "-s", "read-only", "--json"]
        reads = json.loads((ROOT / "adapters/read-tools.json").read_text())["tools"]
        for setting in (
            "features.apps=false", "features.hooks=false", "features.shell_tool=false", "features.plugins=false",
            "features.skill_mcp_dependency_install=false", 'web_search="disabled"',
            'mcp_servers.rootly.command="python3"', "mcp_servers.rootly.args=" + json.dumps(server_args),
            "mcp_servers.rootly.enabled_tools=" + json.dumps(reads),
            'mcp_servers.rootly.default_tools_approval_mode="approve"',
        ):
            command.extend(["-c", setting])
        command.append(PROMPT)
    with tempfile.TemporaryDirectory(prefix="rootly-permissions-") as workspace, trace.open("x") as stdout, \
            (output / f"{client}.stderr").open("x") as stderr:
        process = subprocess.run(command, cwd=workspace, stdout=stdout, stderr=stderr, timeout=180)
    audit_events = [json.loads(line) for line in audit.read_text().splitlines()] if audit.exists() else []
    events = [json.loads(line) for line in trace.read_text().splitlines() if line.startswith("{")]
    result = inspect_result(client, audit_events, events, process.returncode)
    result["client_version"] = subprocess.check_output([client, "--version"], text=True).strip()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = [run(client, output) for client in ("claude", "codex")]
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if all(result["passed"] for result in results) else 1)
