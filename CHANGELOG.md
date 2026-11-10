# Changelog

## 1.1 — unreleased

- Update repository metadata, install commands, and release links to
  `rootlyhq/agent-skills` following the repository transfer.
- Use Rootly publisher metadata across generated platform manifests and include
  public privacy and terms URLs for OpenAI review.
- Clarify pending marketplace availability and the remote MCP submission path.
- Request all toolsets in server read-only mode on bundled MCP connections,
  retaining the client read-tool allowlists.
- Preserve the seven canonical skills and read-only workflows; no legacy write
  actions are restored.

## 1.0 — 2026-10-16

- Seven read-only skills for incident work: incident response, alert triage,
  deploy checks, service health, on-call, incident communications, and
  retrospectives.
- One plugin for Claude Code, Codex, Cursor, and Devin, with Rootly's hosted MCP
  server bundled. Sign in once with OAuth; there are no API keys to manage.
- Slash-command aliases such as `/rootly:respond`, `/rootly:oncall`, and
  `/rootly:retro` in Claude Code and Cursor.
- Read-only tool allowlists for Claude Code and Codex, so an agent in a shared
  session cannot page, edit, or publish.
- Answers separate what Rootly records show from inference and leave
  operational decisions to people.

This release replaces the earlier Rootly plugins for Claude Code and Cursor. It
does not include their write actions yet; read `docs/migration.md` before
switching.
