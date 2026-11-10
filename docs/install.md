# Install and test

This release contains seven read-only skills. It does not restore the older plugins'
write actions. Use a separate test session rather than replacing an existing
production installation until you have checked the migration notes.

## Local Claude Code test

Use the sanitized release folder, then load it:

```sh
claude --plugin-dir /absolute/path/to/rootly
```

The plugin exposes `/rootly:incident-response`, `/rootly:alert-triage`,
`/rootly:deploy-check`, `/rootly:service-health`, `/rootly:on-call`,
`/rootly:incident-communications`, and `/rootly:retrospective`.
Short aliases such as `/rootly:respond` and `/rootly:retro` route to the same files.
Use `/mcp` to authenticate Rootly through the client. Never paste credentials
into a prompt or commit them to this package.

For a persistent local installation, add the sanitized folder as a marketplace:

```sh
claude plugin marketplace add /absolute/path/to/rootly
claude plugin install rootly@rootly-agent-skills --scope local
```

## Local Codex test

The sanitized package includes a local marketplace. Codex reads the root
`plugin.json` (Agent Plugins format) with its `extensions.com.openai` listing
metadata and the root `mcp.json`; verified with Codex CLI 0.162.1. With the
Codex CLI:

```sh
codex plugin marketplace add /absolute/path/to/rootly
codex plugin add rootly@rootly-agent-skills
```

Start a fresh session and invoke a discovered skill, for example
`$rootly:incident-response` (standalone skills use `$incident-response`). Plugin discovery/installation and Rootly authentication
are separate checks. If a client does not expose plugin-bundled MCP, configure
the documented Rootly endpoint through that client's MCP settings and sign in.

To inspect what Codex derives from the package without installing it:

```sh
python3 tools/scripts/check_codex_discovery.py /absolute/path/to/rootly /tmp/empty-workspace
```

The public ChatGPT and Codex directory uses one plugin submission. Because this
plugin includes a hosted MCP server, select **Create plugin → With MCP** in the
[OpenAI plugins dashboard](https://platform.openai.com/plugins), configure
`https://mcp.rootly.com/mcp?toolsets=all&readonly=true`, and attach the exported
skills to the same draft. Preserve these query parameters in the portal.
A ZIP upload alone does not register or verify the remote MCP server. Domain
verification, OAuth configuration, reviewer access, a demo, and review cases
must be completed before submission. See the
[official submission guide](https://developers.openai.com/plugins/deploy/submission).
The directory requires `logo` and `composerIcon` (square, at
least 48 by 48) and caps `displayName` and `shortDescription` at 30 characters;
`tools/scripts/build_package.py` generates values within those limits.

## Cursor

The repository root `plugin.json` conforms to the Agent Plugins specification,
so Cursor loads the skills and `mcp.json` as-is. The `.cursor-plugin/plugin.json`
manifest adds the Cursor-format component set (skills, commands, MCP) and the
marketplace logo; the slash-command aliases in `adapters/cursor/commands/`
mirror the Claude aliases with plugin-root-relative paths.

For a local checkout, point Cursor at this repository. For the public listing,
the repository must be public on GitHub and is submitted at
cursor.com/marketplace/publish; the logo is `assets/logo.svg` (relative path, as
the submission checklist prefers). Cursor does not expand the Agent Plugins
`${PLUGIN_ROOT}`/`${PLUGIN_DATA}` variables inside `mcp.json`; this package does
not use them.

## Devin

Devin loads this repository through its plugin support (CLI, Desktop, and cloud
sessions). The `.devin-plugin/plugin.json` manifest takes precedence and
declares the skills directory and the `.mcp.json` Rootly server
(streamable HTTP). Local install for authoring:

```sh
devin plugins install --local /absolute/path/to/agent-skills
```

Once the repository is pushed to GitHub, `devin plugins install
rootlyhq/agent-skills` installs it to the signed-in scope. In the web app,
Customize → Plugins → Add plugin also accepts a repository or an uploaded
`.zip` of a `dist/` export; the export excludes contributor files. After
indexing, open the plugin's entry under Customize → MCPs and Connect the
`rootly` server — installing the plugin does not authorize the Rootly
connection. Skills then appear as `/rootly:incident-response` and the other
`<plugin>:<skill>` commands.

The Devin-format manifest makes the repository's `AGENTS.md` an always-on rule
in sessions where the plugin is installed. That file holds contributor
instructions; it is harmless but irrelevant to end users. The `dist/` export
excludes it, so `.zip` installs are unaffected.

## Read-only restrictions

The bundled connection requests
`https://mcp.rootly.com/mcp?toolsets=all&readonly=true`. The server's
[toolset documentation](https://github.com/rootlyhq/rootly-mcp-server#toolsets)
describes `readonly=true` as a per-connection guard that hides/refuses write
tools and rejects non-GET requests to the Rootly API. `toolsets=all` preserves
the read tools needed across all seven workflows; `core` alone is insufficient.
This configuration is not live deployment validation or an account-wide
permission change. Reconnect after updating the URL and verify the actual tool
inventory. Other connectors or standalone entries may use a different URL.

Use the generated allowlists in `adapters/read-tools.json` and client restriction
examples in `adapters/` with an isolated session. Claude's `dontAsk` policy denies
unapproved tools; its allow list is not a standalone deny boundary in other modes.
Codex's `enabled_tools` restricts the named MCP server, not unrelated connections
or shell/browser tools. Consult `docs/safety.md` before production use.

Claude Code specifics, verified with Claude Code 2.1.296:

- The plugin server is `plugin:rootly:rootly`. It has its own OAuth identity:
  sign in once with `/mcp` in an interactive session or
  `claude mcp login plugin:rootly:rootly` from the project directory. The
  `claude plugin eval` sandbox cannot reach that login.
- A sign-in attempt that fails is cached in `~/.claude/mcp-needs-auth-cache.json`
  and non-interactive sessions then skip the server. If `claude mcp list` shows it
  Connected but a session reports needs-auth, remove that server's entry from the
  cache file.
- If the account also has the claude.ai Rootly connector, Claude Code suppresses
  the plugin server as a duplicate and the model sees the connector's tools
  (`mcp__claude_ai_Rootly__*`). The generated allow list covers all three
  namespaces; the standalone `rootly` and plugin namespaces are not reachable
  in that case.

Codex specifics, verified with Codex CLI 0.162.0:

- The plugin's MCP server exists only after `codex plugin add`; enabling the
  plugin in `config.toml` alone loads skills but no server.
- Plugin server settings must use the full plugin id,
  `[plugins."rootly@rootly-agent-skills".mcp_servers.rootly]`. A key with the bare
  plugin name is silently ignored, so it does not apply the client filter.
  The bundled URL's server read-only request is a separate layer; an unrestricted
  alternate connection may expose writes. On the command line pass the id unquoted:
  `-c plugins.rootly@rootly-agent-skills.mcp_servers.rootly.enabled_tools=[...]`.
- A standalone `[mcp_servers.rootly]` entry takes precedence over the plugin's
  server of the same name, even when disabled. If you already connect to Rootly
  that way, the standalone entry is what the model uses; restrict it with the
  `[mcp_servers.rootly]` section of `adapters/codex/readonly.toml`, including
  its read-only URL.
- OAuth tokens are stored per server name. A plugin server named `rootly` reuses
  an existing standalone `rootly` login; a differently named server needs its own
  `codex mcp login <name>`.

## Verify

Confirm skill discovery, authenticate, read a minimal permitted record, then try
a synthetic scenario without write tools available. A successful install or
schema check is not proof of correct incident judgment.
