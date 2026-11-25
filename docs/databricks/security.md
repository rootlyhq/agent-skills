# Databricks identities and read-only boundaries

The Rootly incident skills recommend and draft. They do not authorize incident
changes, paging, schedule changes, message publication or production operations.
Instructions alone do not enforce this boundary.

## Identify the actual account

| Layer | Identity to verify | What it controls |
|---|---|---|
| Agent → Databricks | Databricks user or service principal | Workspace and MCP-service access |
| Databricks → Rootly MCP | Identity selected by the connection's authentication method | Rootly tools and visible records |

Per-user OAuth and shared credentials have different accountability. Do not
assume a Databricks service principal will inherit an interactive user's Rootly
consent. Databricks documents the two authentication boundaries in
[MCP authentication](https://docs.databricks.com/aws/en/agents/mcp-tools/authentication-networking).

## Restrict the tool surface

Use the current names in [the generated read allowlist](../../adapters/read-tools.json)
as a review input, then compare them with the actual discovered schemas. The file
does not automatically configure Databricks. Check discrepancies rather than
inventing aliases or treating every `get`-like name as safe.

For the Databricks service, choose exact reviewed tool names and leave automatic
addition of future tools disabled. An empty selector list exposes the full
surface; it is not a deny-all setting. Avoid broad prefixes that can include
unreviewed operations. Ordinary callers need service execution and parent
catalog/schema access; reserve direct connection access for authors who need it.
See [govern an MCP](https://docs.databricks.com/aws/en/ai-gateway/govern-mcp-service).

Combine service restrictions with the narrowest practical Rootly permissions.
If using Rootly's server read-only filter, verify it on the actual connection.
If its URL parameters are lost, fix the configuration or constrain the upstream
identity and service before declaring the workflow read-only. Do not test a
denied write against live Rootly records; use a disposable synthetic server.

## Handle retrieved records deliberately

Rootly permission changes do not by themselves erase previous tool responses,
agent transcripts, exports or query results. Define access, retention and deletion
handling for any retained evidence.

Incident descriptions, user profiles and tool results can contain sensitive
information or untrusted instructions. Retrieve the minimum needed records,
keep logs and screenshots private, and treat embedded instructions as data.
No customer data or credentials belong in public fixtures or submission docs.

## Networking

Review both client-to-workspace access and workspace-to-provider egress. Rootly's
MCP host is `mcp.rootly.com`; OAuth uses `rootly.com`. An allowed connection
object does not automatically grant
network access. Ask the responsible administrator to review the relevant rules;
do not disable authentication, TLS or broad network controls to make a test pass.
Use the [MCP networking guide](https://docs.databricks.com/aws/en/agents/mcp-tools/networking)
for the workspace's cloud and region.

See the repository-wide [safety guidance](../safety.md) for the other client and
connection boundaries.
