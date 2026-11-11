# Rootly AI skill tools

Verified against the public MCP source tests and bundled API schema at
[commit `a518a00d4f5aec36b6fa970e52222d4d583d6025`](https://github.com/rootlyhq/rootly-mcp-server/tree/a518a00d4f5aec36b6fa970e52222d4d583d6025),
reviewed 2026-11-11. This is source verification, not proof that these tools are
available or authorized in the current session. The server groups them in `ai`.
Inspect the connected schema; generated query parameter names can differ from
the HTTP spelling below. Do not invent aliases or unsupported filters.

| Need | Tool | Access | Inputs and constraints |
|---|---|---|---|
| Find an existing skill | `list_ai_skills` | read | Schema-supported search/slug, enabled, source or invocable_by filters; inspect pagination and returned scope |
| Inspect stored content | `get_ai_skill` | read | id is a returned skill ID or a verified slug |
| Inspect available revisions | `list_ai_skill_versions` | read | ai_skill_id is a returned ID or verified slug |
| Read one revision | `get_ai_skill_version` | read | ai_skill_id and integer version from the actual history |
| Save an authorized new skill | `create_ai_skill` | write | data.type=ai_skills; attributes.name, description and body; enabled=false by default |

The API stores Markdown instructions in `body`; it does not require a repository
or a directory of SKILL.md files. Create attributes optionally include `slug`,
`enabled`, `invocable_by` and `owner_user_id`. Invocation sources are `model`,
`user` and `automation`; they select callers, not tool permissions. Do not invent
their defaults or change them on the user's behalf. The owner must belong to the
organization. Omit owner changes unless explicitly selected and verified.

Do not send tool grants or relationships. Fields such as `source`,
`source_template_key`, `source_template_version` and `current_version` describe
server-managed state; they are not creation inputs for this workflow. Skill
versions contain content, not grants. Do not present a skill as permission to
access a tool or claim it is active from its version number.

The MCP source also exposes update and automation operations. This workflow does
not permit them. Its optional authoring profiles list only these five tools.
A read-only connection hides/refuses creation. If tools or team entitlements are
missing, report the limitation and retain the draft; do not claim creation.
