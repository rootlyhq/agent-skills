#!/usr/bin/env python3
"""Read-only Fable review with retained prompt, model identity and native trace.

No MCP, shell, plugins or edit tools. Uses existing Claude authentication; does
not copy credentials. Review output is private and never a release artifact.
"""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def review(prompt_path, output, timeout=1800, model="fable"):
    output.mkdir(parents=True, exist_ok=False)
    prompt = f"Review repository: {ROOT}\n\n" + prompt_path.read_text()
    (output / "prompt.md").write_text(prompt)
    command = ["claude", "-p", prompt, "--model", model,
               "--no-session-persistence", "--restricted", "--setting-sources", "",
               "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
               "--disable-slash-commands", "--tools", "Read,Glob,Grep",
               "--permission-mode", "dontAsk", "--add-dir", str(ROOT),
               "--settings", '{"permissions":{"allow":["Read","Glob","Grep"]}}',
               "--output-format", "stream-json", "--verbose"]
    metadata = {"client_version": subprocess.check_output(["claude", "--version"], text=True).strip(),
                "requested_model": model, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    timed_out = False
    with tempfile.TemporaryDirectory(prefix="rootly-review-") as workspace:
        with (output / "trace.jsonl").open("x") as stdout, (output / "stderr").open("x") as stderr:
            try:
                exit_code = subprocess.run(command, cwd=workspace, stdout=stdout, stderr=stderr,
                                           timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                exit_code = None
    events = []
    for line in (output / "trace.jsonl").read_text().splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # A terminated process may leave a partial final stream event.
                if not timed_out:
                    raise
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    final = next((e for e in reversed(events) if e.get("type") == "result"), {})
    models = sorted({e["message"]["model"] for e in events if e.get("type") == "assistant" and e.get("message", {}).get("model")})
    metadata.update(exit_code=exit_code, timed_out=timed_out, timeout_seconds=timeout,
                    model=init.get("model"), message_models=models,
                    tools=init.get("tools"), mcp_servers=init.get("mcp_servers"),
                    completed=not timed_out and bool(final) and not final.get("is_error"))
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (output / "review.md").write_text(final.get("result", "") + "\n")
    print(json.dumps(metadata, indent=2))
    if exit_code != 0 or not metadata["completed"] or not models or any(model not in m for m in models):
        raise RuntimeError(f"Review did not complete with {model}; inspect retained trace")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=int, default=1800, help="Review deadline in seconds")
    parser.add_argument("--model", default="fable", choices=("fable", "opus", "sonnet"),
                        help="Reviewer model; the actual assistant model is verified afterwards")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    review(args.prompt.resolve(), args.output.resolve(), args.timeout, args.model)
