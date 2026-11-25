"""Select Microsoft's packaged tools from a reviewed MCP tools/list response."""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = "adapters/microsoft/toolDescription.json"
SOURCE = "adapters/microsoft/toolDescription.source.json"
REPOSITORY = "https://github.com/rootlyhq/rootly-mcp-server"
TOOLS = frozenset("""
cancel_investigation check_responder_availability create_incident create_incident_action_item
find_related_incidents get_alert get_alert_by_short_id get_current_user get_escalation_policy
get_incident get_incident_meeting_transcripts get_incident_retrospective get_investigation
get_oncall_handoff_summary get_oncall_schedule_summary get_oncall_shift_metrics get_schedule_shifts
get_server_version get_shift_incidents get_team get_user list_alert_events list_alert_groups
list_alerts list_endpoints list_escalation_policies list_incident_action_items list_incident_alerts
list_incident_events list_incidents list_investigations list_schedules list_services list_severities
list_shifts list_status_pages list_teams list_users search_incidents start_investigation
suggest_solutions update_incident
""".split())


def encode(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def select(response):
    """Preserve wire contracts; omit one redundant endpoint path from help text."""
    tools = response.get("tools", [])
    names = [tool["name"] for tool in tools]
    if len(names) != len(set(names)) or not TOOLS <= set(names):
        raise ValueError("MCP discovery has duplicate names or missing Microsoft tools")
    selected = []
    for tool in sorted(tools, key=lambda value: value["name"]):
        if tool["name"] not in TOOLS:
            continue
        if (not isinstance(tool.get("description"), str)
                or not isinstance(tool.get("inputSchema"), dict)
                or tool["inputSchema"].get("type") != "object"
                or not isinstance(tool.get("annotations"), dict)):
            raise ValueError("MCP tool requires its description, inputSchema and annotations")
        entry = json.loads(json.dumps({key: tool[key] for key in
                                      ("name", "description", "inputSchema", "annotations")}))
        if entry["name"] == "get_user":
            # The redundant API path matches the public-tree scanner's local
            # user-directory pattern. Keep the argument instructions intact.
            parameter = entry["inputSchema"]["properties"]["id"]
            parameter["description"] = re.sub(
                r" \(fills `\{id\}` in [^)]+\)", "", parameter["description"]
            )
        selected.append(entry)
    return {"tools": selected}


def verify(files):
    data = files[CATALOG]
    source = json.loads(files[SOURCE])
    if (source.get("repository") != REPOSITORY
            or not re.fullmatch(r"[0-9a-f]{40}", source.get("commit", ""))
            or source.get("sha256") != hashlib.sha256(data).hexdigest()):
        raise ValueError("Microsoft tool catalog source or checksum mismatch")
    if encode(select(json.loads(data))) != data:
        raise ValueError("Microsoft tool catalog differs from the reviewed selection")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-list", required=True, type=Path,
                        help="Metadata-only JSON tools/list result from the reviewed server")
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        parser.error("Require the exact reviewed MCP source commit")
    data = encode(select(json.loads(args.tools_list.read_bytes())))
    (ROOT / CATALOG).write_bytes(data)
    (ROOT / SOURCE).write_bytes(encode({
        "repository": REPOSITORY, "commit": args.source_commit,
        "sha256": hashlib.sha256(data).hexdigest(),
    }))


if __name__ == "__main__":
    main()
