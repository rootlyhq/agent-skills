#!/usr/bin/env python3
"""Read-only Codex review with retained prompt, model identity and native trace.

The session ignores the user's Codex configuration, so no MCP connection,
plugin, personality or web search is inherited; only the existing authentication
is reused. The sandbox is read-only. Review output is private and never a
release artifact. A completed review is one reviewer's opinion, not clearance.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def review(prompt_path, output, timeout=1800, model="gpt-6-astra"):
    output.mkdir(parents=True, exist_ok=False)
    prompt = f"Review repository: {ROOT}\n\n" + prompt_path.read_text()
    (output / "prompt.md").write_text(prompt)
    command = ["codex", "exec", "--model", model, "--sandbox", "read-only",
               "--cd", str(ROOT), "--skip-git-repo-check", "--ephemeral",
               "--ignore-user-config", "--ignore-rules", "--json",
               "--output-last-message", str(output / "review.md"), prompt]
    metadata = {"client_version": subprocess.check_output(["codex", "--version"], text=True).strip(),
                "requested_model": model, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "user_config_loaded": False, "sandbox": "read-only"}
    timed_out = False
    with (output / "trace.jsonl").open("x") as stdout, (output / "stderr").open("x") as stderr:
        try:
            exit_code = subprocess.run(command, cwd=output, stdout=stdout, stderr=stderr,
                                       stdin=subprocess.DEVNULL, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            timed_out, exit_code = True, None
    events = []
    for line in (output / "trace.jsonl").read_text().splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                if not timed_out:  # A killed process can leave one partial event.
                    raise
    # Count tool-call items, not the text: a reviewer reading this file would
    # otherwise look like an MCP caller.
    items = [event.get("item", {}) for event in events if isinstance(event.get("item"), dict)]
    metadata.update(
        exit_code=exit_code, timed_out=timed_out, timeout_seconds=timeout,
        thread_id=next((event.get("thread_id") for event in events if event.get("thread_id")), None),
        # `codex exec --json` does not report the model per event. Only the
        # requested flag is evidence here, not an observed assistant identity.
        model_identity_source="requested_flag",
        event_types=sorted({event.get("type", "") for event in events}),
        item_types=sorted({item.get("type", "") for item in items}),
        # Distinct items: one call can appear as both started and completed.
        mcp_tool_calls=len({item.get("id") for item in items
                            if item.get("type") == "mcp_tool_call"}),
        review_sha256=hashlib.sha256((output / "review.md").read_bytes()).hexdigest()
        if (output / "review.md").exists() else None,
        completed=not timed_out and exit_code == 0 and (output / "review.md").exists(),
    )
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))
    if not metadata["completed"] or metadata["mcp_tool_calls"]:
        raise RuntimeError("Review did not complete cleanly; inspect the retained trace")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=int, default=1800, help="Review deadline in seconds")
    parser.add_argument("--model", default="gpt-6-astra")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    review(args.prompt.resolve(), args.output.resolve(), args.timeout, args.model)
