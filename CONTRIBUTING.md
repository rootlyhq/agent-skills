# Contributing

Use Python 3.15.2 for development, as recorded in `.python-version`. The tooling
also supports Python 3.12–3.14; CI checks those versions separately. This is a
skills repository with Python maintenance tools, not a Python distribution to
publish to PyPI.

## Local checks

```sh
make setup
make check
```

`make setup` creates `.venv` and installs the exact versions in
`tools/requirements-dev.txt`. When changing Python versions, create a fresh
virtual environment. To keep an existing environment untouched, choose a
different ignored path, for example
`make setup VENV=tools/tests/results/dev-venv PYTHON=python3.15`.

Ruff checks undefined and unused names, import ordering, and modern Python
syntax. `make lint-fix` applies safe fixes outside the calibration-pinned judge
files. It does not rewrite skill instructions or fixture evidence. Keep public
marker exception lines intact; the public-tree scan validates those exact lines.

## Canonical files and generated outputs

Keep workflow instructions in `skills/`, shared templates in `tools/templates/`,
and generation logic in `tools/scripts/`. After changing a canonical source,
run `make generate`, inspect the generated diff, and run `make check`.

Platform adapters route to canonical skills rather than carrying their own copy
of the instructions. Keep the 1.x workflows read-only. Do not edit output
contracts or introduce new workflows as incidental tooling cleanup.

## Evidence and model tests

The three judge/contract/gate scripts and their rubric, labels, and fixtures are
hash-pinned by `tools/tests/behavior/fidelity/judge-agreement.json`. Any edit,
including import sorting or comments, requires a fresh successful calibration.
Do not refresh hashes by hand. Ordinary static tests do not establish calibration.

The model matrix uses authenticated local Claude and Codex clients and makes
model calls. Run it explicitly using [the evaluation procedure](tools/tests/README.md).
Keep the exact exported package fixed during a run. Retain failures and record
client/model versions; a collection error is not an answer pass. Store raw
traces only under ignored `tools/tests/results/`. Release clearance also
requires the model gate and semantic review in that procedure.

## Dependency maintenance and CI

Dependabot checks the pinned Python tools and SHA-pinned GitHub Actions weekly.
Minor/patch updates are grouped; major updates stay separate. Updates follow
the repository's review and check requirements; no auto-merge is configured.

The required `static` job runs on the development Python version. Compatibility
jobs run the static suite on the older supported versions. Model runs and live
Rootly access are not part of ordinary pull-request CI.

The configured public-tree scan requires `ROOTLY_SKILLS_PRIVATE_MARKERS` in CI
or the ignored local `.private-markers` file. Dependabot-triggered workflows
use Dependabot secrets, not ordinary Actions secrets: provision the same-named
Dependabot secret if those PRs need to pass the configured scan. Otherwise a
maintainer must perform the trusted review described in
[the release procedure](docs/releasing.md). Do not expose secrets with
`pull_request_target` or weaken the scan for bots or forks.

## Publishing changes

Run `make public-check` before staging or publishing public content. Never commit
credentials, planning documents, personal attribution, or raw test output.
Use the commit convention and release steps in [releasing](docs/releasing.md).
Creating a local export does not authorize a release tag or marketplace submission.
