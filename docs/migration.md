# Migration to 1.1

Version 1.1 updates distribution metadata after the transfer to
`rootlyhq/agent-skills`. Use that repository for new installations. Existing
GitHub URLs redirect to it; the previous repository name must remain unused to
preserve those redirects. Marketplace updates are pending.

Bundled MCP connections now request all toolsets with `readonly=true`. Reconnect
after upgrading and check any standalone Rootly connection that may take
precedence; it needs the same URL parameters and client restrictions. See
`docs/install.md` and `docs/safety.md` for the documented server guard and its scope.

This release is read-only; it does not restore full write parity with earlier Rootly plugins.
Keep your existing installation available until your workflows have been tested.
Do not enable both versions in one session: duplicate names or connections can
make it unclear which version handled a request.

Canonical workflow names are now incident-response, alert-triage, deploy-check,
service-health, on-call, incident-communications, and retrospective. Claude
aliases route common older commands to these skills without duplicating their
instructions. `handoff` distinguishes shift handoff from commander handoff.

Severity/status changes, alert acknowledgment, posting updates, coverage overrides,
and action-item creation are unavailable. `cover`, `swap`, `announce`, and `action`
produce proposals or drafts, not writes. There is no production deploy executor.

This package does not include the old token-based session/deploy hooks or helper
agents. Rootly MCP is OAuth-first; repository files contain no user credentials.
Cursor, Devin, and ChatGPT marketplace listings are not implied by Claude/Codex
CLI tests.

Rollback: disable this plugin in the client and re-enable the previous one.
No Rootly state migration is required because this release does not write state.
