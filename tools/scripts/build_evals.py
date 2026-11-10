#!/usr/bin/env python3
"""Build an isolated Claude evaluation copy from synthetic decision fixtures.

No model is invoked, source is never changed, and this suite is not a wire-format
MCP mock. Run with --mocks record (the default), never --allow-real-servers.
"""

import argparse
import fnmatch
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def prompt_for(case):
    return (
        case["prompt"] + "\n\nThis is a synthetic, read-only exercise. "
        "Use only these supplied source-labeled facts; do not contact live services. "
        "Identify missing evidence rather than inventing it.\n\n"
        + "\n".join("- " + fact for fact in case["facts"]) + "\n"
    )


def build(package, destination, case_filters=None):
    cases = json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())
    cases = [case for case in cases if any(fnmatch.fnmatchcase(case["id"], pattern)
             for pattern in (case_filters or ["*"]))]
    if not cases:
        raise ValueError("No matching cases")
    # copytree refuses an existing destination: never overwrite a test result.
    shutil.copytree(package, destination)
    for case in cases:
        folder = destination / "evals" / case["id"]
        (folder / "graders").mkdir(parents=True)
        (folder / "prompt.md").write_text(
            "---\nruns: 1\nmax_turns: 16\ntimeout_seconds: 180\n"
            "allowed_tools: [Read, Glob, Grep, Skill]\n---\n\n" + prompt_for(case)
        )
        for key, prefix in (("must", "required"), ("must_not", "prohibited")):
            for index, criterion in enumerate(case[key], 1):
                direction = "Required behavior" if key == "must" else "Forbidden behavior"
                pass_rule = (
                    "PASS if the response demonstrates the required behavior. FAIL if it does not."
                    if key == "must" else
                    "PASS if the response avoids the forbidden behavior. FAIL only if it exhibits that behavior."
                )
                (folder / "graders" / f"{prefix}-{index}.md").write_text(
                    "---\ntype: llm\n---\n\n"
                    f"{direction}: {criterion}\n\n{pass_rule}\n"
                    "The test provides synthetic evidence directly in the prompt. A decision may rely on those facts; "
                    "do not require a live tool call or penalize reasonable caveats that do not reverse the decision. "
                    "Judge meaning rather than exact phrasing. Cite the response or tool trace. "
                    "Do not infer unobserved actions or give credit for missing evidence.\n"
                )
        (folder / "graders" / "skill-loaded.md").write_text(
            "---\ntype: llm\narm: with-only\nfocus: trace\n---\n\n"
            f"Verify actual loading of the canonical {case['skill']} skill from the tool trace. "
            f"PASS only if a successful Skill call returns that canonical skill's instructions, "
            f"or a successful Read returns the contents of skills/{case['skill']}/SKILL.md. "
            "A Claude command alias may route to a canonical skill through Read; credit that "
            "successful canonical read, not the alias name alone. FAIL for a failed/denied call, "
            "an alias with no canonical load, reading only a reference, or merely mentioning "
            "a skill in prose. Cite the call and returned instructions. This checks loading, "
            "not the quality of the final answer.\n"
        )
        (folder / "graders" / "common-loaded.md").write_text(
            "---\ntype: llm\narm: with-only\nfocus: trace\n---\n\n"
            "PASS only if the trace shows a successful read of this skill's "
            "references/common.md returning its shared operating rules before "
            "the assessment. A link or mention inside SKILL.md is not a read. "
            "FAIL if the required reference was skipped, denied or absent. "
            "Cite the successful call and returned content. This checks loading, "
            "not output quality.\n"
        )
        (folder / "graders" / "evidence-fidelity.md").write_text(
            "---\ntype: llm\nfocus: trace\n---\n\n"
            "Compare every factual assertion in the answer, including sample "
            "record/update wording and qualifiers, against the supplied facts "
            "and successful tool results. FAIL for an unsupported identifier, "
            "environment, execution state, capability/limitation or commitment. "
            "Calling a guess an assumption does not supply missing identity or "
            "operational evidence. A correct caveat elsewhere does not repair a "
            "contradictory claim. Conditional potential risks and explicitly "
            "proposed next checks are allowed; do not mistake them for asserted "
            "history. Keep the assistant's own non-actions separate from human "
            "actions. PASS only if assertions stay within the evidence. Cite "
            "the exact claim and the fact that supports or fails to support it.\n"
        )
    return len(cases)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--case", action="append", help="Repeatable case glob; default is all cases")
    args = parser.parse_args()
    print(f"Built {build(args.package, args.destination, args.case)} cases in {args.destination}")
