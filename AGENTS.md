# Project instructions

## Skills

Keep canonical skills in `skills/`. Platform adapters stay thin and never copy
skill instructions. Treat practitioner recommendations as conditional guidance,
distinguish customer policy from defaults, and preserve the plugin's read-only
scope.

## Evidence

Skills must not present inference as fact. Run the static suite and, for output
changes, the evidence-fidelity gate described in `tools/tests/README.md`.

## What stays out of this repository

This repository is public. Do not add planning documents, telemetry, interview
material, personal attribution, credentials, or raw test traces. Test traces
belong in the ignored `tools/tests/results/`. `tools/scripts/check_public_tree.py` runs in
CI and fails on known private markers.

## Provider publishing context

Microsoft 365 Copilot Cowork packaging and validation are documented in
`docs/microsoft-copilot.md`. Keep current submission receipts and continuation
notes private. Databricks MCP procedures are in `docs/databricks/README.md`.
Keep partner correspondence, case-study plans and submission notes in ignored
`tools/tests/results/<submission>/HANDOFF.md` or outside the
checkout; they must not enter release exports or the public tree. Never store
reviewer credentials in those notes. A fresh clone will not contain local notes;
verify provider status in its portal before taking publication actions.


## Commits

Use Conventional Commits, `type(scope): summary`, as described in
`docs/releasing.md`. Release commits are exactly `chore(release): v<VERSION>`.
Check a message before committing with `python3 tools/scripts/check_commit_messages.py`.

## Pinned files

`tools/tests/behavior/fidelity/judge-agreement.json` records hashes of
`tools/scripts/fidelity_judge.py`, `fidelity_contract.py`, `fidelity_gate.py`,
`fidelity_matrix.py`, `fidelity_inputs.py` and the fidelity rubric, labels,
fixtures and deterministic expectations. Any edit, even a comment, makes the
judge calibration stale and requires a new model run. The judge and contract scripts resolve
their paths from `tools/`, not the repository root; leave that as is.
