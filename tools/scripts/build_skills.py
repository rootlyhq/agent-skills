#!/usr/bin/env python3
"""Generate self-contained shared references and skill UI metadata."""

import argparse
import sys
from pathlib import Path

import yaml
from package_config import MCP_URL

ROOT = Path(__file__).resolve().parents[2]


def generated_files():
    shared = {path.name: path.read_text() for path in sorted((ROOT / "tools/templates").glob("*.md"))}
    for entry in sorted((ROOT / "skills").glob("*/SKILL.md")):
        metadata = yaml.safe_load(entry.read_text().split("---", 2)[1])
        name = metadata["name"]
        for filename, content in shared.items():
            if name == "skill-authoring" and filename == "common.md":
                content = (ROOT / "tools/templates/authoring/common.md").read_text()
            yield entry.parent / "references" / filename, content
        ui = {
            "interface": {
                "display_name": "Rootly " + name.replace("-", " ").title(),
                "short_description": metadata["metadata"]["short-description"],
                "default_prompt": f"Use ${name} to help with this Rootly workflow.",
            },
            "dependencies": {"tools": [{
                "type": "mcp", "value": "rootly",
                "description": "Rootly incident and on-call data",
                "transport": "streamable_http", "url": MCP_URL,
            }]},
            "policy": {"allow_implicit_invocation": True},
        }
        # Quote strings, leaving mapping keys unquoted and booleans native.
        def render(value, indent=0):
            import json
            lines = []
            if isinstance(value, dict):
                for key, child in value.items():
                    if isinstance(child, (dict, list)):
                        lines.append(" " * indent + key + ":")
                        lines.extend(render(child, indent + 2))
                    else:
                        lines.append(" " * indent + key + ": " + json.dumps(child))
            elif isinstance(value, list):
                for child in value:
                    block = render(child, indent + 2)
                    block[0] = " " * indent + "- " + block[0].lstrip()
                    lines.extend(block)
            return lines
        yield entry.parent / "agents/openai.yaml", "\n".join(render(ui)) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    mismatches = []
    for path, content in generated_files():
        if args.check:
            if not path.exists() or path.read_text() != content:
                mismatches.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    if mismatches:
        print("Out of date: " + ", ".join(mismatches), file=sys.stderr)
        return 1
    print("Generated skill resources are current." if args.check else "Generated skill resources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
