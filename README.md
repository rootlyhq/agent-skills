# Rootly agent skills

[![Claude Code](https://img.shields.io/badge/Claude_Code-8D6FDE?style=flat-square&logo=claude&logoColor=white)](#claude-code) [![Cursor](https://img.shields.io/badge/Cursor-8D6FDE?style=flat-square&logo=cursor&logoColor=white)](#cursor) [![Codex](https://img.shields.io/badge/Codex-8D6FDE?style=flat-square&logo=data:image/svg%2Bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjMuNSAzLjUgMTYuNSAxNi41Ij48cGF0aCBmaWxsPSIjZmZmIiBkPSJNOS45NDQ5NCA5LjU5MTYzVjguMTMyMjdDOS45NDQ5NCA4LjAwOTM1IDkuOTkxMDUgNy45MTcxMyAxMC4wOTg1IDcuODU1NzVMMTMuMDMyNyA2LjE2NTk5QzEzLjQzMjEgNS45MzU1OCAxMy45MDgzIDUuODI4MSAxNC4zOTk4IDUuODI4MUMxNi4yNDMyIDUuODI4MSAxNy40MTA4IDcuMjU2NzcgMTcuNDEwOCA4Ljc3NzUxQzE3LjQxMDggOC44ODUgMTcuNDEwOCA5LjAwNzkyIDE3LjM5NTMgOS4xMzA4M0wxNC4zNTM3IDcuMzQ4ODRDMTQuMTY5NCA3LjI0MTM1IDEzLjk4NSA3LjI0MTM1IDEzLjgwMDcgNy4zNDg4NEw5Ljk0NDk0IDkuNTkxNjNaTTE2Ljc5NjMgMTUuMjc1NVYxMS43ODgzQzE2Ljc5NjMgMTEuNTczMiAxNi43MDQgMTEuNDE5NiAxNi41MTk3IDExLjMxMjFMMTIuNjY0IDkuMDY5M0wxMy45MjM2IDguMzQ3MjVDMTQuMDMxMSA4LjI4NTg3IDE0LjEyMzQgOC4yODU4NyAxNC4yMzA4IDguMzQ3MjVMMTcuMTY1IDEwLjAzN0MxOC4wMDk5IDEwLjUyODcgMTguNTc4MiAxMS41NzMyIDE4LjU3ODIgMTIuNTg3QzE4LjU3ODIgMTMuNzU0NCAxNy44ODcgMTQuODI5OCAxNi43OTYzIDE1LjI3NTNWMTUuMjc1NVpNOS4wMzg2MSAxMi4yMDMxTDcuNzc4OTYgMTEuNDY1OEM3LjY3MTQ2IDExLjQwNDUgNy42MjUzNSAxMS4zMTIyIDcuNjI1MzUgMTEuMTg5M1Y3LjgwOThDNy42MjUzNSA2LjE2NjEzIDguODg1MDEgNC45MjE3NiAxMC41OTAyIDQuOTIxNzZDMTEuMjM1NCA0LjkyMTc2IDExLjgzNDQgNS4xMzY4OSAxMi4zNDE1IDUuNTIwODlMOS4zMTUyNiA3LjI3MjE4QzkuMTMwOTcgNy4zNzk2OCA5LjAzODc1IDcuNTMzMjggOS4wMzg3NSA3Ljc0ODQxVjEyLjIwMzNMOS4wMzg2MSAxMi4yMDMxWk0xMS43NSAxMy43N0w5Ljk0NDk0IDEyLjc1NjJWMTAuNjA1NkwxMS43NSA5LjU5MTc4TDEzLjU1NDkgMTAuNjA1NlYxMi43NTYyTDExLjc1IDEzLjc3Wk0xMi45MDk4IDE4LjQ0QzEyLjI2NDUgMTguNDQgMTEuNjY1NSAxOC4yMjQ5IDExLjE1ODUgMTcuODQwOUwxNC4xODQ3IDE2LjA4OTZDMTQuMzY5IDE1Ljk4MjEgMTQuNDYxMiAxNS44Mjg1IDE0LjQ2MTIgMTUuNjEzNFYxMS4xNTg1TDE1LjczNjMgMTEuODk1OEMxNS44NDM4IDExLjk1NzIgMTUuODg5OSAxMi4wNDk0IDE1Ljg4OTkgMTIuMTcyM1YxNS41NTE5QzE1Ljg4OTkgMTcuMTk1NSAxNC42MTQ4IDE4LjQ0IDEyLjkwOTggMTguNDRaTTkuMjY5MDEgMTUuMDE0NEw2LjMzNDg2IDEzLjMyNDZDNS40ODk5IDEyLjgzMyA0LjkyMTYxIDExLjc4ODUgNC45MjE2MSAxMC43NzQ2QzQuOTIxNjEgOS41OTE3NyA1LjYyODI0IDguNTMxODMgNi43MTg4NiA4LjA4NjNWMTEuNTg4N0M2LjcxODg2IDExLjgwMzkgNi44MTEwOSAxMS45NTc1IDYuOTk1MzggMTIuMDY1TDEwLjgzNTkgMTQuMjkyM0w5LjU3NjIxIDE1LjAxNDRDOS40Njg3MiAxNS4wNzU4IDkuMzc2NDkgMTUuMDc1OCA5LjI2OTAxIDE1LjAxNDRaTTkuMTAwMTMgMTcuNTMzN0M3LjM2NDI2IDE3LjUzMzcgNi4wODkxOSAxNi4yMjc5IDYuMDg5MTkgMTQuNjE0OUM2LjA4OTE5IDE0LjQ5MiA2LjEwNDYgMTQuMzY5MSA2LjExOTg4IDE0LjI0NjJMOS4xNDYxIDE1Ljk5NzVDOS4zMzAzOSAxNi4xMDUgOS41MTQ4MyAxNi4xMDUgOS42OTkxMiAxNS45OTc1TDEzLjU1NDkgMTMuNzcwMlYxNS4yMjk1QzEzLjU1NDkgMTUuMzUyNCAxMy41MDg4IDE1LjQ0NDYgMTMuNDAxMyAxNS41MDZMMTAuNDY3MSAxNy4xOTU4QzEwLjA2NzcgMTcuNDI2MiA5LjU5MTQ4IDE3LjUzMzcgOS4wOTk5OSAxNy41MzM3SDkuMTAwMTNaTTEyLjkwOTggMTkuMzYxNkMxNC43Njg1IDE5LjM2MTYgMTYuMzIgMTguMDQwNiAxNi42NzM1IDE2LjI4OTNDMTguMzkzOSAxNS44NDM4IDE5LjUgMTQuMjMwOCAxOS41IDEyLjU4NzJDMTkuNSAxMS41MTE4IDE5LjAzOTEgMTAuNDY3MyAxOC4yMDk2IDkuNzE0NTRDMTguMjg2NCA5LjM5MTkyIDE4LjMzMjYgOS4wNjkzIDE4LjMzMjYgOC43NDY4MkMxOC4zMzI2IDYuNTUwMTQgMTYuNTUwNSA0LjkwNjM0IDE0LjQ5MjEgNC45MDYzNEMxNC4wNzc0IDQuOTA2MzQgMTMuNjc3OSA0Ljk2NzcyIDEzLjI3ODUgNS4xMDYwNUMxMi41ODcyIDQuNDMwMTEgMTEuNjM0NyA0IDEwLjU5MDIgNEM4LjczMTQgNCA3LjE3OTk2IDUuMzIxMDMgNi44MjY1IDcuMDcyMzJDNS4xMDYwNSA3LjUxNzg2IDQgOS4xMzA4MyA0IDEwLjc3NDVDNCAxMS44NDk4IDQuNDYwOCAxMi44OTQ0IDUuMjkwMzUgMTMuNjQ3MUM1LjIxMzU0IDEzLjk2OTcgNS4xNjc0MyAxNC4yOTIzIDUuMTY3NDMgMTQuNjE0OEM1LjE2NzQzIDE2LjgxMTQgNi45NDk0MSAxOC40NTUyIDkuMDA3OTIgMTguNDU1MkM5LjQyMjYxIDE4LjQ1NTIgOS44MjIwNCAxOC4zOTM5IDEwLjIyMTUgMTguMjU1NkMxMC45MTI3IDE4LjkzMTUgMTEuODY1MSAxOS4zNjE2IDEyLjkwOTggMTkuMzYxNloiLz48L3N2Zz4%3D)](#codex) [![Devin](https://img.shields.io/badge/Devin-8D6FDE?style=flat-square&logo=data:image/svg%2Bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjQyLjIgNDIuMCAzNDIuMiAzNDIuMiI%2BPHBhdGggZmlsbD0iI2ZmZiIgZD0iTTcwIDE1OS4zMzNWOTEuMzQ3MUM3MCA4OC4zNTkyIDcxLjU5NCA4NS41OTgzIDc0LjE4MTYgODQuMTA0NEwxMzMuMDQzIDUwLjEyMDVDMTM1LjYzMSA0OC42MjY1IDEzOC44MTkgNDguNjI2NSAxNDEuNDA3IDUwLjEyMDVMMjAwLjI2OSA4NC4xMDQ0QzIwMi44NTYgODUuNTk4MyAyMDQuNDUgODguMzU5MiAyMDQuNDUgOTEuMzQ3MVYxMjYuMDY4QzIwNC43MDggMTM3LjYwNiAyMTAuODA2IDE0OC43MzQgMjIxLjUzMSAxNTQuOTI2QzIzMi4yNTYgMTYxLjExNyAyNDQuOTQyIDE2MC44MzQgMjU1LjA2MyAxNTUuMjg5TDI4NS4xMzIgMTM3LjkyOUMyODcuNzE5IDEzNi40MzUgMjkwLjkwNyAxMzYuNDM1IDI5My40OTUgMTM3LjkyOUwzNTIuMzU3IDE3MS45MTNDMzU0Ljk0NCAxNzMuNDA2IDM1Ni41MzggMTc2LjE2NyAzNTYuNTM4IDE3OS4xNTVWMjQ3LjEyM0MzNTYuNTM4IDI1MC4xMTEgMzU0Ljk0NCAyNTIuODcyIDM1Mi4zNTcgMjU0LjM2NkwyOTMuNDk1IDI4OC4zNUMyOTAuOTA3IDI4OS44NDQgMjg3LjcxOSAyODkuODQ0IDI4NS4xMzIgMjg4LjM1TDI1NS4zMDYgMjcxLjEzQzI0NS4xNDYgMjY1LjQ1NiAyMzIuMzQ0IDI2NS4xMTcgMjIxLjUzNCAyNzEuMzU4QzIxMC44MDkgMjc3LjU1IDIwNC43MTEgMjg4LjY3OCAyMDQuNDUzIDMwMC4yMTVWMzM0LjkyNkMyMDQuNDUzIDMzNy45MTQgMjAyLjg1OSAzNDAuNjc1IDIwMC4yNzEgMzQyLjE2OUwxNDEuNDEgMzc2LjE1M0MxMzguODIyIDM3Ny42NDcgMTM1LjYzNCAzNzcuNjQ3IDEzMy4wNDYgMzc2LjE1M0w3NC4xODQ1IDM0Mi4xNjlDNzEuNTk2OSAzNDAuNjc1IDcwLjAwMjggMzM3LjkxNCA3MC4wMDI4IDMzNC45MjZWMjY2Ljk1OUM3MC4wMDI5IDI2My45NzEgNzEuNTk2OSAyNjEuMjEgNzQuMTg0NSAyNTkuNzE2TDEzMy4wNDYgMjI1LjczMkMxMzUuNjM0IDIyNC4yMzggMTM4LjgyMiAyMjQuMjM4IDE0MS40MSAyMjUuNzMyTDE3MS41NDcgMjQzLjEzMkMxODEuNjU2IDI0OC42MzggMTk0LjMwNiAyNDguOTA2IDIwNS4wMDUgMjQyLjcyOUMyMTUuODE1IDIzNi40ODggMjIxLjkyMiAyMjUuMjMxIDIyMi4wODggMjEzLjU5NUMyMjEuODMgMjAyLjA1NyAyMTUuNzMyIDE4OS43MzcgMjA1LjAwOCAxODMuNTQ1QzE5NC4yODMgMTc3LjM1MyAxODEuNTk3IDE3Ny42MzYgMTcxLjQ3NiAxODMuMTgxTDE0MS4yNjkgMjAwLjcyQzEzOC42NyAyMDIuMjI5IDEzNS40NjEgMjAyLjIyOCAxMzIuODY0IDIwMC43MTZMNzQuMTU3NiAxNjYuNTYyQzcxLjU4MzUgMTY1LjA2NSA3MCAxNjIuMzExIDcwIDE1OS4zMzNaIi8%2BPC9zdmc%2B)](#devin)

Rootly's plugin for AI coding agents: Claude Code, Codex, Cursor, and Devin.
This repository is the canonical source for the skills and generated platform
adapters. Marketplace listings are separate distribution channels.
It connects your agent to your Rootly account and teaches it how to work an
incident, so you can ask "what is going on with checkout right now?", "is it
safe to deploy this?", or "who is on call for payments?" and get answers
grounded in your real incidents, alerts, services, and schedules.

Connection and server capabilities are documented in the
[Rootly MCP server repository](https://github.com/rootlyhq/rootly-mcp-server).

## What's inside

- **Seven skills.** Each is a `SKILL.md` workflow with its own reference
  material: which Rootly records to pull, how to weigh evidence, what the
  answer should look like, and a worked example. They cover incident response,
  alert triage, deploy checks, service health, on-call, incident
  communications, and retrospectives.
- **Rootly MCP connection.** The plugin bundles Rootly's hosted MCP server, so
  after a one-time OAuth sign-in your agent reads live incidents, alerts,
  services, schedules, and retrospectives. No API keys to manage.
- **Slash commands.** Short aliases such as `/rootly:respond`,
  `/rootly:oncall`, and `/rootly:retro` route to the right skill in Claude Code
  and Cursor.
- **Read-only guardrails.** The bundled connection requests server read-only
  mode, with additional read-tool allowlists for Claude Code and Codex.
  See [safety](docs/safety.md) for the boundaries and verification steps.

## How it helps

- **During an incident:** impact, recent changes, related incidents, and
  mitigation options with the evidence behind each, plus who to pull in.
- **Before a deploy:** GO / CAUTION / NO-GO from incident history, service
  health, and current on-call coverage.
- **On call:** coverage lookups, complete shift handoffs, and swap options.
- **Afterwards:** stakeholder updates drafted for the right audience, and
  retrospective evidence with facilitation questions.

## Skills

| Skill | What it does |
|---|---|
| [Incident response](skills/incident-response/SKILL.md) | Investigate impact and recent changes; recommend mitigation and responders |
| [Alert triage](skills/alert-triage/SKILL.md) | Recommend a new incident, attachment, wait, or dismissal — with evidence |
| [Deploy check](skills/deploy-check/SKILL.md) | GO / CAUTION / NO-GO with reasons; staffing warnings kept separate |
| [Service health](skills/service-health/SKILL.md) | Errors, latency, and traffic against baselines, plus ownership context |
| [On-call](skills/on-call/SKILL.md) | Coverage lookups, complete shift handoffs, provisional swaps |
| [Incident comms](skills/incident-communications/SKILL.md) | Audience-specific drafts — no invented impact or recovery estimates |
| [Retrospective](skills/retrospective/SKILL.md) | Evidence and facilitation questions; humans own the conclusions |

## Install

Each client installs one plugin named `rootly` that bundles the seven skills,
slash-command aliases, and the Rootly MCP server. Pick your client:

### Claude Code

```sh
claude plugin marketplace add rootlyhq/agent-skills
claude plugin install rootly@rootly-agent-skills --scope local
```

### Codex

```sh
codex plugin marketplace add rootlyhq/agent-skills
codex plugin add rootly@rootly-agent-skills
```

### Cursor

Use a local checkout of this repository as described in
[installation](docs/install.md#cursor). The Cursor Marketplace listing is pending;
the repository includes both Agent Plugins and Cursor manifests.

### Devin

Works in the Devin CLI, Desktop, and cloud sessions.

```sh
devin plugins install rootlyhq/agent-skills
```

### Skills only, any agent

```sh
npx skills add rootlyhq/agent-skills
```

This installs the skills as plain `SKILL.md` files without the bundled MCP
server or aliases; connect Rootly MCP through your client yourself.

Then invoke a skill, for example `/rootly:incident-response` in Claude Code
and Devin or `$rootly:incident-response` in Codex. The first call prompts for
Rootly sign-in through the client's MCP flow; never paste a token into chat.
Local checkouts, read-only restrictions, and per-client quirks are in
[installation](docs/install.md).

## Read-only by design

The skills recommend and draft only — they never page responders, modify
incidents, change schedules, publish messages, or act on production. Prompt
instructions are not access controls: apply the client restrictions in
`adapters/` before using live data. See [safety](docs/safety.md) and
[migration](docs/migration.md).

## Status

`1.1` — unreleased consolidation update following the transfer to
`rootlyhq/agent-skills`. The published release is `1.0`. Marketplace updates
are pending. Read-only by design: the earlier plugins' write actions are not
included; see [migration](docs/migration.md).

## License

Apache-2.0. Copyright 2026 Rootly, Inc. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).
