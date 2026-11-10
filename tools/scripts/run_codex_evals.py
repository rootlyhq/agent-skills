#!/usr/bin/env python3
"""Run supplied-facts decisions through native Codex, retaining unscored traces.

Uses discovered native skill input, the client's default model, a fresh ephemeral
thread per case, read-only sandbox, no live MCP, no web, no hooks or other plugins.
Results still require criterion-by-criterion review; completion is not a pass.
"""

import argparse
import fnmatch
import hashlib
import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from build_evals import prompt_for
from codex_client import Client, answer_text
from run_workflow_probes import common_loaded

ROOT = Path(__file__).resolve().parents[2]


def inputs_for(case, skill, invocation):
    prompt = prompt_for(case)
    if skill and invocation == "default-prompt":
        prompt = skill["interface"]["defaultPrompt"] + "\n\n" + prompt
    inputs = [{"type": "text", "text": prompt}]
    if skill and invocation == "explicit":
        inputs.append({"type": "skill", "name": skill["name"], "path": skill["path"]})
    return inputs


def run(case, package, output, with_plugin, invocation="explicit"):
    arm = "with" if with_plugin else "without"
    trace_path = output / f"{case['id']}-{arm}.jsonl"
    final_path = output / f"{case['id']}-{arm}.md"
    if trace_path.exists() or final_path.exists():
        raise FileExistsError(f"Refusing to replace existing run: {trace_path}")
    result = {"case": case["id"], "arm": arm, "status": "error", "trace": str(trace_path),
              "invocation": invocation,
              "prompt_sha256": hashlib.sha256(prompt_for(case).encode()).hexdigest(),
              "fixture_sha256": hashlib.sha256((ROOT / "tools/tests/behavior/cases.json").read_bytes()).hexdigest(),
              "package_inventory_sha256": hashlib.sha256((package / "release-inventory.json").read_bytes()).hexdigest(),
              "client_version": subprocess.check_output(["codex", "--version"], text=True).strip()}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="rootly-codex-eval-") as workspace, trace_path.open("x") as trace:
        client = None
        try:
            client = Client(package, Path(workspace), with_plugin, trace)
            skill = None
            catalog = client.request("skills/list", {"cwds": [workspace], "forceReload": True})
            rootly_skills = [s for row in catalog["data"] for s in row["skills"]
                            if s["name"].startswith("rootly:") and s["enabled"]]
            if with_plugin:
                candidates = [s for s in rootly_skills if s["name"] == "rootly:" + case["skill"]]
                if len(candidates) != 1:
                    raise RuntimeError("Expected exactly one discovered, enabled skill")
                skill = candidates[0]
                result["skill_sha256"] = hashlib.sha256(Path(skill["path"]).read_bytes()).hexdigest()
                prefix = "skills/" + case["skill"] + "/"
                inventory = json.loads((package / "release-inventory.json").read_text())
                for relative, expected in inventory.items():
                    if relative.startswith(prefix):
                        installed = Path(skill["path"]).parent / relative[len(prefix):]
                        if not installed.is_file() or hashlib.sha256(installed.read_bytes()).hexdigest() != expected:
                            raise RuntimeError("Installed skill differs from the requested release: " + relative)
            elif rootly_skills:
                raise RuntimeError("Baseline contaminated by an enabled Rootly skill")
            thread = client.request("thread/start", {
                "cwd": workspace, "sandbox": "read-only", "approvalPolicy": "never", "ephemeral": True,
            })
            result["model"] = thread.get("model")
            result["model_identity_source"] = "thread_start"
            result["skill_path"] = skill["path"] if skill else None
            inputs = inputs_for(case, skill, invocation)
            result["prompt_sha256"] = hashlib.sha256(inputs[0]["text"].encode()).hexdigest()
            if skill and invocation == "default-prompt":
                result["default_prompt"] = skill["interface"]["defaultPrompt"]
            thread_id = thread["thread"]["id"]
            turn = client.request("turn/start", {"threadId": thread_id, "input": inputs})
            result.update(thread_id=thread_id, turn_id=turn["turn"]["id"])
            deadline = time.monotonic() + 180
            final = []
            while time.monotonic() < deadline:
                event = client.receive_turn(thread_id, turn["turn"]["id"], max(0.01, deadline - time.monotonic()))
                if event.get("method") == "item/completed":
                    item = event["params"]["item"]
                    if item.get("type") == "agentMessage":
                        final.append(item)
                if event.get("method") == "turn/completed":
                    result["turn_status"] = event["params"]["turn"]["status"]
                    result["status"] = "completed" if result["turn_status"] == "completed" else "error"
                    break
            else:
                raise TimeoutError("turn")
            answer, visible = answer_text(final)
            final_path.write_text(answer + "\n")
            (output / f"{case['id']}-{arm}-visible.md").write_text(visible + "\n")
            trace.flush()
            events = [json.loads(line) for line in trace_path.read_text().splitlines() if line.startswith("{")]
            result["common_loaded"] = common_loaded("codex", events)
        except Exception as error:
            result["error"] = f"{type(error).__name__}: {error}"
        finally:
            if client:
                client.close()
    result["duration_seconds"] = round(time.monotonic() - started, 2)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--case", action="append", help="Repeatable case glob; default is all cases")
    parser.add_argument("--exclude", default="")
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=1)
    parser.add_argument("--ablation", choices=("none", "with-without"), default="none")
    parser.add_argument("--invocation", choices=("explicit", "implicit", "default-prompt"), default="explicit")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cases = json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())
    selected = [c for c in cases if any(fnmatch.fnmatchcase(c["id"], pattern) for pattern in (args.case or ["*"]))
                and not (args.exclude and fnmatch.fnmatchcase(c["id"], args.exclude))]
    if not selected:
        raise SystemExit("No matching cases")
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run, case, args.package.resolve(), args.output.resolve(), arm, args.invocation)
                   for case in selected
                   for arm in ([True, False] if args.ablation == "with-without" else [True])]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
            try:
                print(json.dumps({"case": result["case"], "arm": result["arm"], "status": result["status"]}), flush=True)
            except BrokenPipeError:
                pass
    if any(result["status"] != "completed" for result in results):
        raise SystemExit(1)
