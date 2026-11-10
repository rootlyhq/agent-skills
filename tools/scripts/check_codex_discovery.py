#!/usr/bin/env python3
"""Inspect native Codex plugin/skill discovery without starting a model turn."""

import argparse
import json
import selectors
import subprocess
import time
from pathlib import Path


def check(package, workspace):
    command = ["codex", "app-server", "--stdio"]
    for setting in (
        'features.apps=false', 'features.hooks=false',
        'plugins._default.enabled=false',
        'plugins.rootly@rootly-agent-skills.enabled=true',
        'plugins.rootly.mcp_servers.rootly.enabled=false',
        'marketplaces.rootly-agent-skills.source_type="local"',
        f'marketplaces.rootly-agent-skills.source={json.dumps(str(package))}',
    ):
        command.extend(["-c", setting])
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, bufsize=1, cwd=workspace)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    count = 0

    def request(method, params):
        nonlocal count
        count += 1
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": count, "method": method, "params": params}) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if not selector.select(timeout=1):
                continue
            line = process.stdout.readline()
            if not line:
                raise RuntimeError("Codex app-server exited")
            value = json.loads(line)
            if value.get("id") == count:
                if "error" in value:
                    raise RuntimeError(value["error"])
                return value["result"]
        raise TimeoutError(method)

    try:
        request("initialize", {"clientInfo": {"name": "rootly-package-check", "version": "1.0"},
                               "capabilities": {"experimentalApi": True}})
        process.stdin.write('{"jsonrpc":"2.0","method":"initialized"}\n')
        process.stdin.flush()
        plugin = request("plugin/read", {"pluginName": "rootly", "marketplacePath": str(package / ".agents/plugins/marketplace.json")})
        skills = request("skills/list", {"cwds": [str(workspace)], "forceReload": True})
        # Only return this package's skill names/errors, not unrelated user skills.
        return {"plugin": plugin, "skills": [
            {"cwd": row.get("cwd"), "skills": [s for s in row.get("skills", []) if s.get("name", "").startswith("rootly:")],
             "errors": [e for e in row.get("errors", []) if "rootly" in str(e)]}
            for row in skills.get("data", [])
        ]}
    finally:
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.package.resolve(), args.workspace.resolve()), indent=2))
