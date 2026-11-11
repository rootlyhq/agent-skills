# Release procedure

Build and check a fresh, allowlisted release package:

```sh
python3 tools/scripts/check_public_tree.py --require-private-markers
python3 tools/scripts/check_release_metadata.py
python3 tools/scripts/build_package.py
python3 tools/scripts/build_package.py --check
python3 tools/scripts/validate_skills.py
python3 -m unittest discover -s tools/tests/static -v
python3 tools/scripts/export_release.py
```

`check_public_tree.py` scans every file git would track, case-insensitively for
private markers and separately for credential patterns. It rejects symlinks,
unreadable and binary files. Only exact reviewed example lines have private-marker
exceptions; credentials are never exempt. Findings withhold the matched value.

Local private markers come from the ignored `.private-markers` file; CI reads
the repository Actions secret `ROOTLY_SKILLS_PRIVATE_MARKERS`, using the same
one-regex-per-line format. The release check and CI fail if neither is configured.
A maintainer must provision that secret without committing or printing its value.
Fork pull requests do not receive repository secrets: their private-marker check
will remain blocked until a trusted maintainer performs the equivalent review.
Do not use `pull_request_target` to expose the secret to untrusted code.
Run the local scan before staging or pushing. Scan the exact index after staging,
and every outgoing commit before pushing:

```sh
python3 tools/scripts/check_public_tree.py --staged --require-private-markers
python3 tools/scripts/check_public_tree.py --range 'origin/main..HEAD' --require-private-markers
```

The index scan reads Git blobs even when working files differ. The range scan
inspects each committed tree, including content removed before the final commit.
An invalid range, unresolved index entry, symlink, submodule or unreadable blob
fails closed. CI also scans the pushed/PR range; it cannot undo disclosure after
a push to a public repository.

Optional local hooks provide these checks before commits and pushes. After
configuring private markers and running `make setup`, enable them with
`git config core.hooksPath .githooks` if this checkout has no existing hook
configuration to preserve. They use `.venv/bin/python`; set
`ROOTLY_SKILLS_PYTHON` to another configured Python environment if needed.
New remote branches scan all reachable history, so an old finding can require
review even if it was already published. Fetch a remote tip that is missing
locally before a push. Hooks supplement review and can be bypassed; they are
not a guarantee against publication mistakes.

The exporter writes a content-addressed directory and deterministic ZIP under
`dist/`. It includes only enumerated runtime and docs files, `skills/`, and
`adapters/`. It rejects symlinks, unexpected file types, private markers and
obvious credential patterns. These checks supplement human review; they are not
a universal secret detector. `release-inventory.json` gives per-file hashes.

Validate and install from the exported directory, not the source checkout.
Keep test traces under the ignored `tools/tests/results/`; they can contain live
Rootly records and never belong in the repository or a release. Inspect the
final ZIP before sharing it.

Creating a local artifact does not publish it. A release is a tagged commit
plus the exported ZIP, after the static suite, current judge calibration, complete
evidence-fidelity matrix and manual semantic review in `tools/tests/README.md` pass.
An export is only a candidate; old matrix results do not clear changed skills.

## Versioning

`VERSION` is the only place a version is typed, and only through
`tools/scripts/bump_version.py`. Everything else derives from it: the generated
manifests through `build_package.py`, the exported artifact
name, the top `CHANGELOG.md` section, the README status line and the migration
title. `check_release_metadata.py` fails when any of these disagree; CI runs it
on every push and again before a release.

Versions are `MAJOR.MINOR`: `1.0`, `1.1`, `1.2`, then `2.0`. No patch digit,
no pre-release suffix.

- **Minor**: the normal release. New skills, references, routes or adapters,
  and fixes to wording, evidence rules or examples. Existing prompts keep working.
- **Major**: a skill is removed or renamed, an output contract changes shape, or
  a workflow gains write actions. Users must re-read the migration notes.

The release tag is `v` plus the exact `VERSION`, on the commit whose changelog
section carries the release date. One tag per version; a tag is never moved.

### Commit messages

Every commit follows [Conventional Commits](https://www.conventionalcommits.org/):
`type(scope): summary`, lowercase, imperative, no trailing period, 72 characters
at most. Types are `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`,
`ci`, `chore` and `revert`; the scope is optional and usually a skill name, such
as `fix(on-call): keep coverage gaps visible`. A `!` after the type or scope
marks a breaking change, which means a major version. CI checks every pushed
commit with `tools/scripts/check_commit_messages.py`.

The changelog stays the curated release notes; commit subjects are for the
history and the compare link in each release.

### Bump

```sh
python3 tools/scripts/bump_version.py 1.1
```

This rewrites `VERSION`, retitles the unreleased changelog section (or opens a
new one when the top section is already dated), updates the README status line
and the migration title, regenerates the manifests and runs the metadata check.
It refuses a malformed version or one that does not follow the current one;
`--allow-downgrade` overrides the ordering check and is only legitimate before
the first release tag exists.
Fill in the changelog entries; the bump is committed together with the release below.

### Release

```sh
python3 tools/scripts/bump_version.py --release   # dates the top changelog section
# run the release checks above
git commit -am "chore(release): v1.1"
git tag -a v1.1 -m v1.1
git push origin main v1.1
```

A release is exactly one commit, `chore(release): v<VERSION>`, holding the
version bump, the dated changelog and the regenerated manifests, with the tag on
that commit. The release workflow refuses a tag on any other commit.

Pushing the tag runs `.github/workflows/release.yml`. It repeats the static
gates, refuses a tag that does not equal `v$VERSION` or a changelog section
still marked unreleased, exports the package and creates a GitHub Release titled
after the tag with three assets: `rootly-v<VERSION>.zip`, its `.sha256`, and
`release-inventory.json`. `tools/scripts/release_notes.py` writes the notes: the
changelog section, which skills changed since the previous tag with a compare
link, the install commands and the archive checksum. The workflow never creates tags,
runs models or publishes to a marketplace. Submissions below are made by hand:
Git-backed listings pin the released source commit, while the OpenAI submission
attaches the exported skills to the remote MCP draft.

## Where each listing is submitted

The GitHub repository must be public first; every listing below points at it
or at the exported ZIP. Claude, Cursor, and OpenAI submission guidance rechecked
on 2026-11-10; Devin and skills.sh notes last checked on 2026-10-16.

| Target | Submission | Notes |
|---|---|---|
| Claude Code, claude.ai, Cowork | Developer portal at https://claude.ai/directory/manage | Requires a paid claude.ai plan (Team/Enterprise: an Owner). Run `claude plugin validate <export> --strict` first. The `claude-plugins-official` marketplace is partner-only. |
| Codex and ChatGPT | Plugins dashboard at https://platform.openai.com/plugins → Create plugin → With MCP | Configure the hosted endpoint and attach the exported skills to the same draft. Domain verification, OAuth, required listing URLs, reviewer access, demo, five positive and three negative review cases, and scans are required; a ZIP alone does not register the MCP server. See [Submit plugins](https://developers.openai.com/plugins/deploy/submission). |
| Cursor | https://cursor.com/marketplace/publish | Manual review; public repo and README required. |
| Devin | No self-serve form | The public marketplace is curated by Cognition; ask via https://app.devin.ai/settings/support or support@cognition.ai. Users can install from the repo directly with `devin plugins install rootlyhq/agent-skills`. |
| skills.sh | None | Listing appears automatically after the first `npx skills add rootlyhq/agent-skills` against the public repo. Only then does the `https://skills.sh/b/rootlyhq/agent-skills` badge resolve; add it to the README after that, not before. |
