# Changelog

## 3.0.0 — unreleased

- Start a unified 3.0.0 version line above the earlier platform-specific plugins.
  This migration uses the canonical skill names and read-only workflows described
  in `docs/migration.md`; legacy write actions are not restored.

- Adopt SemVer and release-please release PRs, retaining explicit approval for
  immutable tags and publication of the exact reviewed release ZIP.
- Update repository metadata, install commands, and release links to
  `rootlyhq/agent-skills` following the repository transfer.
- Use Rootly publisher metadata across generated platform manifests and include
  public privacy and terms URLs for OpenAI review.
- Clarify pending marketplace availability and the remote MCP submission path.
- Request all toolsets in server read-only mode on bundled MCP connections and
  individual skill dependencies, retaining the client read-tool allowlists.
- Scan staged Git blobs and outgoing commit history before publication, with
  optional local hooks and matching CI checks.
- Bind fidelity clearance to the grading implementation, observed judge identity,
  retained prompts, fixture inputs and exact package contents.
- Clarify gaps in supplied excerpts versus complete records, preserve action
  states in illustrative wording, and reinforce the existing answer boundaries.
- Require deploy assessments to load the shared evidence guidance before drafting.
- Explain mitigation decisions without inventing their rationale, comparative
  harm, prerequisites or execution state in handoff guidance.
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
