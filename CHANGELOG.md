# Changelog

## 3.0.0 (2026-11-13)


### Features

* **microsoft:** prepare Copilot packages in release workflows ([#17](https://github.com/rootlyhq/agent-skills/issues/17)) ([f6bbc6d](https://github.com/rootlyhq/agent-skills/commit/f6bbc6d276b10edd0e4ad55e113e01f5ffdcca56))


### Bug Fixes

* **deploy-check:** ground verdicts in deciding evidence ([57c6d34](https://github.com/rootlyhq/agent-skills/commit/57c6d347866d0739d50cd5b29fb9692c46a101d1))
* **evals:** retry invalid judge quotes once ([00f09e8](https://github.com/rootlyhq/agent-skills/commit/00f09e82687450037194d2665d3e93ce35cf737f))
* **evals:** retry invalid judge quotes once ([ac73c17](https://github.com/rootlyhq/agent-skills/commit/ac73c1720436f9084ebce7ee2ad3f23763559f1b))
* **fidelity:** keep inferred reasoning conditional ([2eb4c2f](https://github.com/rootlyhq/agent-skills/commit/2eb4c2f91a50cd75b450832d4bd40e5056793943))
* **fidelity:** preserve evidence scope and required output states ([d9bddce](https://github.com/rootlyhq/agent-skills/commit/d9bddce0f6cc7c25c014ba082fc9025122b23c4f))
* **fidelity:** recalibrate judging and scope focused answers ([22cef35](https://github.com/rootlyhq/agent-skills/commit/22cef3523fb7935e541424c734754a221030a6d4))
* **fidelity:** turn evidence gaps into explicit follow-up checks ([678a102](https://github.com/rootlyhq/agent-skills/commit/678a1021fdb243057714018d5041c01958e15809))
* **incident-response:** ask neutral questions for missing evidence ([4c23be9](https://github.com/rootlyhq/agent-skills/commit/4c23be9ce4a83a135786a004eb43d64b4820b520))
* **incident-response:** keep explanations inside the focused format ([6205cb4](https://github.com/rootlyhq/agent-skills/commit/6205cb4301ed1467026952016bf0a8aa2f27c6b4))
* **incident-response:** preserve decision and assessment evidence ([203df46](https://github.com/rootlyhq/agent-skills/commit/203df46576236515831220995267e700cede3219))
* **incident-response:** preserve evidence in mitigation explanations ([13ba6f0](https://github.com/rootlyhq/agent-skills/commit/13ba6f06c3b5ab1ef9c32aeb912a6093253b257c))
* **incident-response:** separate policy from incident state ([c3a3384](https://github.com/rootlyhq/agent-skills/commit/c3a3384cea5cbf259d3ab3355804346fa3b699e2))
* **metadata:** use Rootly as skill author ([3ef238a](https://github.com/rootlyhq/agent-skills/commit/3ef238a4b7d8eaec8f5a29686a5a1544a2c95ae6))
* **metadata:** use Rootly as skill author ([cb46b31](https://github.com/rootlyhq/agent-skills/commit/cb46b31f8196b4884d7cef3f07ee63ec1db9ebe0))
* **plugin:** consolidate canonical source and read-only setup ([#1](https://github.com/rootlyhq/agent-skills/issues/1)) ([6b51224](https://github.com/rootlyhq/agent-skills/commit/6b5122479ba8ea6be1bdfbac271d85d82796b83b))
* **release:** handle unchanged release PR output ([54f0122](https://github.com/rootlyhq/agent-skills/commit/54f01226d80b247f653321e8399eb9e23d541a43))
* **release:** handle unchanged release PR output ([389a5a0](https://github.com/rootlyhq/agent-skills/commit/389a5a03aa4cec8d6476207a58a8441423853b19))
* **release:** start unified version line at 3.0.0 ([c67ed4b](https://github.com/rootlyhq/agent-skills/commit/c67ed4b0a1fc0129789ae4a53afb5d2e7a282859))
* **release:** start unified version line at 3.0.0 ([1d0407e](https://github.com/rootlyhq/agent-skills/commit/1d0407e4e50867fffcc6be0e67b1157544ebb1d1))
* **skills:** improve evidence fidelity and move CI to Blacksmith ([edbf485](https://github.com/rootlyhq/agent-skills/commit/edbf4857b61f6c50c19afdcda105d016dbc4a6aa))
* **skills:** refresh MCP source verification ([3973b4c](https://github.com/rootlyhq/agent-skills/commit/3973b4c2dc316e71a70ad1ee6ee045818ea680ee))
* **skills:** refresh MCP source verification ([50f3b08](https://github.com/rootlyhq/agent-skills/commit/50f3b08d7f2cc565d680d956c59770ec6bca0bc0))
* **validation:** bind publication and fidelity checks to exact inputs ([810a7c4](https://github.com/rootlyhq/agent-skills/commit/810a7c4b612444d357287a3cceb81f4808cf5a5f))
* **validation:** bind publication and fidelity checks to exact inputs ([85a684b](https://github.com/rootlyhq/agent-skills/commit/85a684b38f8f9daa476b1cd7079300418d89a04f))

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
