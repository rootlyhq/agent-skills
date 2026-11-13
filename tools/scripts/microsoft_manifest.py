"""Thin Microsoft adapter metadata; skill instructions remain canonical."""

APP_ID = "c819ab41-e86d-479e-94e5-30bf776f8691"
MCP_URL = "https://mcp.rootly.com/mcp?toolsets=all"
SKILLS = (
    "alert-triage", "deploy-check", "incident-communications", "incident-response",
    "on-call", "retrospective", "service-health",
)


def manifest(version):
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/teams/vDevPreview/MicrosoftTeams.schema.json",
        "manifestVersion": "devPreview",
        "version": version,
        "id": APP_ID,
        "developer": {
            "name": "Rootly, Inc.", "websiteUrl": "https://rootly.com",
            "privacyUrl": "https://rootly.com/legal/privacy",
            "termsOfUseUrl": "https://rootly.com/legal/terms",
        },
        "name": {"short": "Rootly for Copilot", "full": "Rootly for Copilot"},
        "description": {
            "short": "Incident workflows and Rootly context for Copilot Cowork.",
            "full": (
                "Bring Rootly incident workflows and incident context into Microsoft Copilot Cowork. "
                "Seven skills guide incident investigation, alert triage, deployment risk assessment, "
                "service health reviews, on-call coverage, incident communication drafts, and "
                "retrospectives. The workflows use available evidence, distinguish facts from "
                "hypotheses, and recommend or draft rather than execute operational changes. "
                "A remote MCP connection provides access to Rootly data. A Rootly account with "
                "appropriate permissions and service access, a supported Microsoft 365 Copilot "
                "license, and permission to install this plugin are required. Rootly service "
                "charges may apply. Additional repository or telemetry integrations are optional "
                "and are not included in this package."
            ),
        },
        "icons": {"color": "color.png", "outline": "outline.png"},
        "accentColor": "#8D6FDE",
        "agentSkills": [{"folder": f"./skills/{name}"} for name in SKILLS],
        "agentConnectors": [{
            "id": "rootly", "displayName": "Rootly",
            "description": (
                "Rootly incidents, alerts, services, on-call schedules, and retrospectives "
                "for the Rootly skills."
            ),
            "toolSource": {"remoteMcpServer": {"mcpServerUrl": MCP_URL}},
        }],
    }
