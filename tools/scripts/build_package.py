#!/usr/bin/env python3
"""Generate Claude/Codex packaging from the canonical skills and VERSION."""

import argparse
import json
import re
import sys
from pathlib import Path

from build_skills import generated_files as skill_files
from package_config import MCP_URL

ROOT = Path(__file__).resolve().parents[2]
DESCRIPTION = "Read-only incident response, alert triage, deploy checks, service health, on-call, communications, and retrospectives."
MARKETPLACE = "rootly-agent-skills"
ALIASES = {
    "respond": "incident-response", "incident": "incident-response",
    "alert": "alert-triage", "status": "service-health", "lookup": "service-health",
    "trend": "service-health", "oncall": "on-call", "my": "on-call",
    "swap": "on-call", "cover": "on-call", "brief": "incident-communications",
    "announce": "incident-communications", "retro": "retrospective", "action": "retrospective",
}


def encoded(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def read_tools():
    result = {}
    for entry in sorted((ROOT / "skills").glob("*/references/tools.md")):
        result[entry.parents[1].name] = sorted(set(re.findall(
            r"^\| [^|]+ \| `([^`]+)` \| read \|", entry.read_text(), re.M)))
    return result


def generated_files():
    yield from skill_files()
    version = (ROOT / "VERSION").read_text().strip()
    identity = {
        "name": "rootly", "version": version, "description": DESCRIPTION,
        "author": {"name": "Rootly", "url": "https://rootly.com"},
        "homepage": "https://github.com/rootlyhq/agent-skills",
        "repository": "https://github.com/rootlyhq/agent-skills",
        "license": "Apache-2.0",
        "keywords": ["rootly", "incident-response", "on-call", "read-only"],
    }
    # Codex/ChatGPT listing metadata. The public directory caps displayName and
    # shortDescription at 30 characters and requires logo and composerIcon.
    codex_interface = {
        "displayName": "Rootly",
        "shortDescription": "Read-only incident workflows",
        "longDescription": (
            "Seven read-only workflows for incident work: investigate incidents, triage "
            "alerts, assess deploy risk, check service health, look up on-call coverage, "
            "draft stakeholder updates, and prepare retrospectives. Each skill combines "
            "Rootly records with authorized telemetry and repository context, separates "
            "evidence from hypotheses, and leaves operational decisions with humans. "
            "The skills recommend and draft only: they never page responders, modify "
            "incidents, change schedules, publish messages, or act on production."
        ),
        "developerName": "Rootly",
        "category": "Productivity",
        "capabilities": [
            "Investigate incidents", "Triage alerts", "Assess deploy risk",
            "Check service health", "Look up on-call coverage",
            "Draft incident updates", "Prepare retrospectives",
        ],
        "websiteURL": "https://rootly.com",
        "supportURL": "https://docs.rootly.com/contacting-support",
        "privacyPolicyURL": "https://rootly.com/legal/privacy",
        "termsOfServiceURL": "https://rootly.com/legal/terms",
        "defaultPrompt": [
            "Investigate this incident with Rootly context and recommend mitigation.",
            "Assess the risk of deploying this change using Rootly incident history.",
            "Who is on call for this service right now, and when is the next handoff?",
        ],
        "brandColor": "#8D6FDE",
        "composerIcon": "./assets/logo.svg",
        "logo": "./assets/logo.svg",
    }
    yield ROOT / "plugin.json", encoded({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", **identity,
        "extensions": {"com.openai": {"interface": codex_interface}},
    })
    yield ROOT / ".claude-plugin/plugin.json", encoded({
        **identity, "skills": "./skills/", "commands": "./adapters/claude/commands/",
    })
    # Cursor and Devin document author as {name, email}; drop url for strict validators.
    name_only = {**identity, "author": {"name": identity["author"]["name"]}}
    yield ROOT / ".cursor-plugin/plugin.json", encoded({
        **name_only, "logo": "assets/logo.svg", "skills": "./skills/",
        "commands": "./adapters/cursor/commands/", "mcpServers": "./mcp.json",
    })
    yield ROOT / ".devin-plugin/plugin.json", encoded({
        **name_only, "skills": "./skills/", "mcpServers": "./.mcp.json",
    })
    yield ROOT / "mcp.json", encoded({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
        "mcpServers": {"rootly": {"type": "streamable-http", "url": MCP_URL}},
    })
    yield ROOT / ".mcp.json", encoded({
        "mcpServers": {"rootly": {"type": "http", "url": MCP_URL}},
    })
    yield ROOT / ".claude-plugin/marketplace.json", encoded({
        "name": MARKETPLACE, "owner": {"name": "Rootly"},
        "metadata": {"description": DESCRIPTION, "version": version},
        "plugins": [{"name": "rootly", "source": "./", "description": DESCRIPTION, "version": version}],
    })
    yield ROOT / ".agents/plugins/marketplace.json", encoded({
        "name": MARKETPLACE,
        "interface": {"displayName": "Rootly Agent Skills"},
        "plugins": [{
            "name": "rootly", "source": {"source": "local", "path": "./"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }],
    })
    tools_by_skill = read_tools()
    all_reads = sorted({name for names in tools_by_skill.values() for name in names})
    yield ROOT / "adapters/read-tools.json", encoded({
        "version": version, "skills": tools_by_skill, "tools": all_reads,
    })
    codex = [
        "# Generated read-tool restriction; merge with a dedicated test/session config.",
        "# It restricts this MCP server, not unrelated tools or other connections.",
        "[mcp_servers.rootly]", f'url = "{MCP_URL}"',
        "enabled_tools = " + json.dumps(all_reads), 'default_tools_approval_mode = "approve"',
        "", '[plugins."rootly@' + MARKETPLACE + '".mcp_servers.rootly]',
        "enabled_tools = " + json.dumps(all_reads), 'default_tools_approval_mode = "approve"',
    ]
    yield ROOT / "adapters/codex/readonly.toml", "\n".join(codex) + "\n"
    allowed = ["Read", "Glob", "Grep", "Skill"]
    # Claude suppresses a plugin server that duplicates a claude.ai connector;
    # the connector's tools then carry the third namespace.
    for namespace in ("rootly", "plugin_rootly_rootly", "claude_ai_Rootly"):
        allowed.extend(f"mcp__{namespace}__{name}" for name in all_reads)
    yield ROOT / "adapters/claude/readonly.settings.json", encoded({
        "permissions": {"defaultMode": "dontAsk", "allow": allowed},
    })
    for alias, skill in ALIASES.items():
        yield ROOT / f"adapters/claude/commands/{alias}.md", (
            f"---\ndescription: Rootly {alias}; read-only alias for {skill}\n---\n\n"
            f"Read `${{CLAUDE_PLUGIN_ROOT}}/skills/{skill}/SKILL.md` and follow that workflow.\n"
            "This release recommends or drafts only; it does not execute writes.\n\nRequest: $ARGUMENTS\n"
        )
    yield ROOT / "adapters/claude/commands/handoff.md", (
        "---\ndescription: Prepare a Rootly shift or incident commander handoff\n---\n\n"
        "For shift handoff, read `${CLAUDE_PLUGIN_ROOT}/skills/on-call/SKILL.md`.\n"
        "For incident commander handoff, read `${CLAUDE_PLUGIN_ROOT}/skills/incident-communications/SKILL.md`.\n"
        "If ambiguous, ask which handoff is needed. Follow the selected workflow; do not transfer duties.\n\n"
        "Request: $ARGUMENTS\n"
    )
    yield ROOT / "adapters/claude/commands/setup.md", (
        "---\ndescription: Check Rootly skill installation and connection prerequisites\n---\n\n"
        "Read `${CLAUDE_PLUGIN_ROOT}/docs/install.md`. Identify this client's setup steps,\n"
        "verify available read tools, and explain any missing authentication or read-only restriction.\n"
        "Never ask the user to paste a token into chat or claim a connection worked without checking.\n"
    )
    for alias, skill in ALIASES.items():
        yield ROOT / f"adapters/cursor/commands/{alias}.md", (
            f"---\nname: {alias}\ndescription: Rootly {alias}; read-only alias for {skill}\n---\n\n"
            f"Read `skills/{skill}/SKILL.md` inside this plugin and follow that workflow.\n"
            "This release recommends or drafts only; it does not execute writes.\n\nRequest: $ARGUMENTS\n"
        )
    yield ROOT / "adapters/cursor/commands/handoff.md", (
        "---\nname: handoff\ndescription: Prepare a Rootly shift or incident commander handoff\n---\n\n"
        "For shift handoff, read `skills/on-call/SKILL.md` inside this plugin.\n"
        "For incident commander handoff, read `skills/incident-communications/SKILL.md` inside this plugin.\n"
        "If ambiguous, ask which handoff is needed. Follow the selected workflow; do not transfer duties.\n\n"
        "Request: $ARGUMENTS\n"
    )
    yield ROOT / "adapters/cursor/commands/setup.md", (
        "---\nname: setup\ndescription: Check Rootly skill installation and connection prerequisites\n---\n\n"
        "Read `docs/install.md` inside this plugin. Identify this client's setup steps,\n"
        "verify available read tools, and explain any missing authentication or read-only restriction.\n"
        "Never ask the user to paste a token into chat or claim a connection worked without checking.\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for path, content in generated_files():
        if args.check:
            if not path.is_file() or path.read_text() != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    if stale:
        print("Out of date: " + ", ".join(stale), file=sys.stderr)
        return 1
    print("Package resources are current." if args.check else "Generated package resources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
