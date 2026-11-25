# Troubleshoot the correct integration

First identify whether the failure concerns an MCP service, a coding-agent skill
or a public listing. Each has its own installation and
authorization state.

| Symptom | Check | Useful next evidence |
|---|---|---|
| Provider console unavailable | Provider onboarding and Marketplace role | Provider approval and role state, without credentials |
| Listing cannot be found | Actual published listing and selected exchange | Listing URL and provider-console status |
| DCR setup fails | Discovery, registration, redirect and provider response | HTTP status and sanitized error category |
| Sign-in succeeds but agent calls fail | Both authentication boundaries and network directions | Databricks service login state and request failure category |
| Tool missing | Selected endpoint/profile, service filter and Rootly scope | Actual tool inventory and configuration |
| Tool schema is too large for the model | Selected tools and model limits | Measured inventory for the chosen host/model |
| Tool call returns 401/403 | Login state, resource access and organization | Status and affected read tool, with credentials withheld |
| Some records are missing | Visibility, pagination and requested window | Sanitized counts and continuation state |
| Current on-call cannot be confirmed | Shift permissions, timezone and time window | Authorized live coverage lookup |

## Public discovery checks

These commands use no account token and read no incident records:

```sh
curl --fail --show-error --silent \
  'https://mcp.rootly.com/.well-known/oauth-protected-resource'
curl --fail --show-error --silent \
  'https://rootly.com/.well-known/oauth-authorization-server'
```

Check the advertised authorization server, registration endpoint and PKCE
methods. A reachable metadata document establishes discovery availability only.
It does not prove that a Databricks callback, user consent, refresh or tool call
will succeed.

A healthy unauthenticated MCP request should require authorization. Do not treat
an authentication challenge as a tool failure. Conversely, an unexpected 403
does not identify its cause: capture the client, HTTP status and response type
before deciding whether routing, network policy or the application rejected it.
Do not work around a denial by disabling protections.

## Capture a useful support report

Record the integration, exact source revision or deployed endpoint, client and
runtime versions, time of failure, selected resources and sanitized error. Keep
the actual connection and effective identity clear. Reproduction should retrieve
only a small authorized sample and preserve the original failure.

Exclude passwords, tokens, OAuth codes, cookies, private incident payloads and
opaque cursors from public reports. Describe counts and structural differences
without copying customer values. Keep raw evidence in a private location under
the organization's handling policy.

For Databricks-side connectivity, use its
[network troubleshooting guide](https://docs.databricks.com/aws/en/agents/mcp-tools/networking#troubleshoot-blocked-requests).
For Rootly access and API behavior, use [Rootly support](https://docs.rootly.com/contacting-support).
Public availability problems require checking the provider console, not
reinstalling an unrelated skill ZIP.
