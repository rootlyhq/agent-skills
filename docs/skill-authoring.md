# Create an AI skill inside Rootly

Use `skill-authoring`, or `/rootly:author` in Claude Code and Cursor, to turn a
team procedure into instructions stored as a native Rootly AI skill. No Git
repository synchronization is involved.

For example: "Turn this queue-backlog procedure into a Rootly AI skill. Show me
the draft before creating it." After reviewing the name, description and body,
ask to create that content. The agent searches existing skills, makes one create
call, and reads the returned record. New skills default to disabled; creation
does not execute the instructions or enable an automation.

## Connection permissions

The default bundled Rootly connection requests `readonly=true`. It can inspect
AI skills when the deployed server and account expose those reads, but it cannot
create them. Do not remove that guard from incident workflows to enable authoring.

Use a deliberately configured, separate authoring connection or an already
authorized connection exposing `create_ai_skill`. The server's `ai` toolset
contains additional operations; selecting that toolset alone does not restrict
it to skill creation. The optional client profiles restrict it to four reads
and one write:

- `list_ai_skills`, `get_ai_skill`, `list_ai_skill_versions`, `get_ai_skill_version`
- `create_ai_skill`

The exact set is generated in `adapters/authoring-tools.json`. These files are
opt-in examples, not automatically loaded by the manifests. Review them before
merging them into a dedicated session configuration.

- **Codex:** `adapters/codex/skill-authoring.toml` defines a separate
  `rootly_authoring` server with only those five tools enabled. It does not
  autoapprove the write. Authenticate that server through the client's OAuth flow.
- **Claude Code:** `adapters/claude/skill-authoring.mcp.json` defines that server.
  `skill-authoring.settings.json` preapproves its reads and asks for the create
  tool. For a dedicated session, select these files with `--mcp-config` and
  `--settings`; `--strict-mcp-config` excludes other MCP configurations. A plugin
  install alone does not load this optional authoring configuration.
- **Cursor, Devin and hosted clients:** deliberately configure a separate
  authoring connection or use an existing authorized one. Restrict its tools to
  the list above where the host supports it; retain write approval and review the
  actual inventory. The Claude/Codex profiles do not enforce another host's rules.
  Provider-managed connections may require publisher or administrator setup.

Client restrictions do not change the account's server permissions or restrict
other connections. Prefer an account role with the narrowest needed permissions.
If creation is unavailable, the skill returns the draft and the missing access
step. It must not silently reconnect, broaden credentials or use an HTTP bypass.

## What gets saved

Rootly stores the reviewed name, description and Markdown `body`. The workflow
sets `enabled: false` unless the user explicitly authorizes enabling with the
reviewed content. It does not choose owner or invocation settings on the user's
behalf, attach tool grants, update an existing skill or run an automation.
Enabling or running an already-created skill is outside this authoring workflow.

After a timeout, creation may have happened. Inspect an exact candidate before
deciding whether to retry. A successful response followed by a failed readback
means creation succeeded but stored-content verification is incomplete.

Source and schema verification are documented in the skill's tool reference.
They do not establish live tool availability, OAuth access, successful creation,
or useful model behavior in a customer's account.
