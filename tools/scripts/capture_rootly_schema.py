#!/usr/bin/env python3
"""Capture the authenticated Rootly read-tool schema without model/tool execution.

Run only with user authorization to use their existing Rootly connection.
Does not initiate OAuth, request broader credentials, or invoke tools. The output
directory must be new and private (normally ignored tools/tests/results/).
"""

import argparse
import json
import tempfile
from pathlib import Path

from codex_client import Client

ROOT = Path(__file__).resolve().parents[2]


def summarize(pages, requested):
    servers = [server for page in pages for server in page["data"]]
    if not servers or any(server["name"] != "rootly" for server in servers):
        raise ValueError("Expected only the requested Rootly server")
    tools = {name: tool for server in servers for name, tool in server["tools"].items()}
    return {
        "requested_count": len(requested),
        "advertised_count": len(tools),
        "missing_tools": sorted(set(requested) - tools.keys()),
        "unexpected_tools": sorted(tools.keys() - set(requested)),
        "unverified_read_only": sorted(name for name, tool in tools.items()
                                      if tool.get("annotations", {}).get("readOnlyHint") is not True),
        "auth_status": sorted({server["authStatus"] for server in servers}),
        "tool_calls": 0,
        "scope": "Configured read-tool allowlist; not an unfiltered server inventory or execution test",
    }


def capture(output):
    allowlist = json.loads((ROOT / "adapters/read-tools.json").read_text())["tools"]
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="rootly-schema-") as workspace, (output / "trace.jsonl").open("x") as trace:
        client = Client(ROOT, Path(workspace), False, trace, rootly_read_tools=allowlist)
        try:
            pages = []
            cursor = None
            while True:
                params = {"serverName": "rootly", "detail": "toolsAndAuthOnly", "limit": 100}
                if cursor:
                    params["cursor"] = cursor
                page = client.request("mcpServerStatus/list", params, timeout=60)
                pages.append(page)
                cursor = page.get("nextCursor")
                if not cursor:
                    break
                if len(pages) >= 10:
                    raise RuntimeError("Unexpected schema pagination; stop rather than expand scope")
            (output / "schema.json").write_text(json.dumps(pages, indent=2) + "\n")
            summary = summarize(pages, allowlist)
            (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(json.dumps(summary, indent=2))
        finally:
            client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    capture(parser.parse_args().output.resolve())
