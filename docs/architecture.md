# Architecture

The `skills/` directories are the canonical implementation. Every client
(Claude Code, Codex, Cursor, Devin, and skills.sh installs) reads the same skill
bodies, references and worked examples. Claude and Cursor aliases are thin
routing files, not parallel implementations. Rootly MCP supplies live data;
authorized telemetry, repository and policy sources supply context it may lack.

`VERSION` and skill/tool metadata generate the platform manifests, marketplaces,
MCP declarations, aliases and read-tool lists. Shared templates are copied into
each skill so a single installed directory remains self-contained. The small
core routes to evidence, responder, company-policy and repository detail only
when the task needs it.

The package keeps machinery separate from customer-owned content. Customer
service mapping, runbooks and severity/escalation policy are not baked into the
package.

Generated allowlists are inputs to client restrictions, not a security claim by
themselves. See `docs/safety.md`. Tests distinguish static structure, installation,
fixture behavior and live reads; no one category substitutes for the others.
