# Connect Rootly MCP through Databricks

Use this path for agents that need Rootly context on demand. It does not create
an analytics copy of the Rootly account.

## Connection choices

| Setting | Value |
|---|---|
| Transport | Streamable HTTP |
| Classic Rootly endpoint | `https://mcp.rootly.com/mcp` |
| Per-user sign-in | OAuth Dynamic Client Registration, when supported in the workspace |
| Rootly authorization host | `https://rootly.com` |
| Rootly discovery metadata | `https://mcp.rootly.com/.well-known/oauth-protected-resource` |

This repository's default direct connection uses
`https://mcp.rootly.com/mcp?toolsets=all&readonly=true`. Before using that URL
through a Databricks connection, verify that its query parameters survive
registration, discovery and calls. Do not describe a plain `/mcp` connection as
server-enforced read-only. Follow [permission setup](security.md).

Rootly also provides Code Mode, which uses discovery and execution meta-tools.
That changes what Databricks can select and govern as an individual tool. The
classic endpoint is the starting point for this guide; changing surfaces requires
an explicit tool-governance and compatibility review. See the
[Rootly server documentation](https://github.com/rootlyhq/rootly-mcp-server#toolsets).

## Register and test

Use a Unity Catalog-enabled workspace in a supported region. The registering
identity needs parent catalog/schema access, permission to create a service,
and permission to create or use its connection.

1. In **Unity Gateway → MCPs**, add an external MCP server.
2. Select its catalog/schema and create a connection to Rootly using DCR.
3. Discover tools, sign in when prompted, and choose the intended Rootly organization.
4. Select the reviewed read tools; save the service.
5. In AI Playground, attach that service and verify a bounded, authorized read.

The current [Databricks registration guide](https://docs.databricks.com/aws/en/ai-gateway/register-mcp-service)
documents the exact privileges and UI. Interface names can vary by workspace.
An installable Marketplace listing is an alternative distribution route, described
in [Databricks' consumer guide](https://docs.databricks.com/aws/en/marketplace/get-started-consumer#get-access-to-external-mcp-servers).

For DCR, allow automatic discovery and client registration. Do not substitute a
placeholder client ID, copy another customer's OAuth application, or assume a
maintainer's Rootly session authorizes other users. Each user must authorize the
correct Rootly identity. See [HTTP connection authentication](https://docs.databricks.com/aws/en/query-federation/http).

## Connect a supported agent

The service has a Databricks URL of this form:

```text
https://<workspace-hostname>/ai-gateway/mcp-services/<catalog>.<schema>.<service>
```

It uses Databricks authentication on the inbound side and the configured Rootly
identity on the outbound side. A Rootly token is not a Databricks workspace token.
Follow the [supported-agent setup guides](https://docs.databricks.com/aws/en/ai-gateway/coding-agent-supported-agents)
for the chosen client, then install the canonical Rootly skills separately.

Verify tool discovery before asking for an incident analysis. Select a small
read task, inspect its actual schema, and use only the returned identifiers and
supported parameters. Retain private evidence of a successful call; a model's
claim that it connected is insufficient.

## Optional Python inventory check

After configuring Databricks authentication and installing the libraries in the
[official Python guide](https://docs.databricks.com/aws/en/agents/custom-agents/use-mcp-tools),
this example lists tool names without reading incident records:

```python
from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksMCPClient

client = DatabricksMCPClient(
    server_url="https://<workspace-hostname>/ai-gateway/mcp-services/<catalog>.<schema>.<service>",
    workspace_client=WorkspaceClient(),
)
print([tool.name for tool in client.list_tools()])
```

The example is documentation, not a completed workspace test. Do not place tokens
in its URL or source. Tool discovery is also not evidence that each tool works.
