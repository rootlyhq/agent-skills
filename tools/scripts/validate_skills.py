#!/usr/bin/env python3
"""Check portable skill structure and scenario integrity, not model behavior."""

import json
import re
import sys
from pathlib import Path

import yaml
from build_skills import generated_files

ROOT = Path(__file__).resolve().parents[2]
SKILLS = {
    "incident-response", "alert-triage", "deploy-check", "service-health",
    "on-call", "incident-communications", "retrospective",
}
SECTIONS = [
    "Purpose", "Use when / not when", "Inputs", "Jobs", "Repo leg",
    "Data honesty", "Output", "Writes", "Routes",
]


def validate():
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    version = (ROOT / "VERSION").read_text().strip()
    entries = sorted((ROOT / "skills").glob("*/SKILL.md"))
    check({p.parent.name for p in entries} == SKILLS, "Expected all seven canonical skills")
    for entry in entries:
        skill = entry.parent
        content = entry.read_text()
        match = re.match(r"\A---\n(.*?)\n---\n", content, re.S)
        check(match is not None, f"{skill.name}: missing frontmatter")
        if not match:
            continue
        try:
            metadata = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            errors.append(f"{skill.name}: invalid YAML: {exc}")
            continue
        if not isinstance(metadata, dict):
            errors.append(f"{skill.name}: frontmatter must be a mapping")
            continue
        check(set(metadata) == {"name", "description", "license", "metadata"},
              f"{skill.name}: unexpected/missing portable frontmatter keys")
        check(metadata.get("name") == skill.name, f"{skill.name}: name mismatch")
        description = metadata.get("description", "")
        check(isinstance(description, str) and 20 <= len(description) <= 1024,
              f"{skill.name}: invalid description")
        detail = metadata.get("metadata", {})
        check(detail.get("version") == version, f"{skill.name}: version drift")
        check(detail.get("access") == "read", f"{skill.name}: access must be read")
        check(len(content.splitlines()) < 150, f"{skill.name}: exceeds line budget")
        check(re.findall(r"^## (.+)$", content, re.M) == SECTIONS,
              f"{skill.name}: incorrect sections/order")
        for filename in ("common.md", "tools.md", "output.md", "example.md"):
            check((skill / "references" / filename).is_file(),
                  f"{skill.name}: missing references/{filename}")
        for document in skill.rglob("*.md"):
            text = document.read_text()
            check(not re.search(r"\bTODO\b|_Type here_|/Users/|practitioner-workbook", text),
                  f"{document.relative_to(ROOT)}: placeholder or private source reference")
            for destination in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if re.match(r"https?://|#", destination):
                    continue
                target = (document.parent / destination.split("#", 1)[0]).resolve()
                check(target.is_relative_to(skill.resolve()) and target.is_file(),
                      f"{document.relative_to(ROOT)}: missing or nonportable link {destination}")
        tool_doc = skill / "references/tools.md"
        if tool_doc.exists():
            rows = re.findall(r"^\| [^|]+ \| `([^`]+)` \| ([^|]+) \|", tool_doc.read_text(), re.M)
            check(bool(rows), f"{skill.name}: empty tool mapping")
            check(len(rows) == len({name for name, _ in rows}), f"{skill.name}: duplicate tool")
            for name, access in rows:
                check(re.fullmatch(r"[a-z]+(?:_[a-z0-9]+)+", name) is not None,
                      f"{skill.name}: non-snake-case tool {name}")
                check(access.strip() == "read", f"{skill.name}: non-read tool {name}")
        ui_path = skill / "agents/openai.yaml"
        check(ui_path.is_file(), f"{skill.name}: missing generated UI metadata")
        if ui_path.exists():
            ui = yaml.safe_load(ui_path.read_text())
            interface = ui["interface"]
            check(25 <= len(interface["short_description"]) <= 64,
                  f"{skill.name}: UI description length")
            check(f"${skill.name}" in interface["default_prompt"],
                  f"{skill.name}: UI prompt must name the skill")
    for path, expected in generated_files():
        check(path.exists() and path.read_text() == expected,
              f"{path.relative_to(ROOT)}: generated resource drift")

    cases = json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())
    ids = {case["id"] for case in cases}
    by_id = {case["id"]: case for case in cases}
    check(len(ids) == len(cases), "Duplicate scenario IDs")
    check({case["skill"] for case in cases} == SKILLS, "Scenario coverage missing a skill")
    for case in cases:
        for field in ("id", "skill", "prompt", "facts", "must", "must_not", "contrast", "contrast_reason"):
            check(bool(case.get(field)), f"{case['id']}: missing {field}")
        check(case.get("contrast") in ids and case.get("contrast") != case["id"],
              f"{case['id']}: invalid counterexample link")
        reason = case.get("contrast_reason")
        check(isinstance(reason, str) and bool(reason.strip()),
              f"{case['id']}: contrast_reason must explain the evidence/decision change")
        counterpart = by_id.get(case.get("contrast"))
        if counterpart is not None:
            check(counterpart.get("contrast") == case["id"],
                  f"{case['id']}: contrast must be reciprocal")
            check(counterpart.get("skill") == case.get("skill"),
                  f"{case['id']}: contrast must use the same skill")
            check(set(counterpart.get("facts", [])) != set(case.get("facts", [])),
                  f"{case['id']}: contrast must change the supplied evidence")
            check(set(counterpart.get("must", [])) != set(case.get("must", [])),
                  f"{case['id']}: contrast must change the required reasoning or decision")
        for field in ("facts", "must", "must_not"):
            check(isinstance(case.get(field), list) and
                  all(isinstance(item, str) and item.strip() for item in case[field]),
                  f"{case['id']}: {field} must contain nonempty strings")
        # Optional: the output format this question routes to, checked per run.
        check(case.get("format", "brief") in ("brief", "focused", "deploy"),
              f"{case['id']}: unknown declared output format")
        if counterpart is not None and "format" in case:
            check(counterpart.get("format") == case["format"],
                  f"{case['id']}: a contrast pair must route to the same output format")
    return errors, len(entries), len(cases)


if __name__ == "__main__":
    errors, skill_count, case_count = validate()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"PASS: {skill_count} skills; {case_count} scenario definitions; generated resources current.")
    print("Static checks only. No model behavior, live MCP, OAuth, or platform installation tested.")
