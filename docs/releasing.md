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

## Versioning and release PRs

Versions are stable SemVer: `MAJOR.MINOR.PATCH`, for example `1.1.0`,
`1.1.1`, `1.2.0`, then `2.0.0`. The historical `v1.0` tag and changelog
section remain unchanged. The first canonical SemVer release is `v1.1.0`.

- **Patch:** compatible fixes, including evidence wording and tooling fixes.
- **Minor:** new skills, references, routes or adapters that preserve compatibility.
- **Major:** removed/renamed skills, changed output-contract shape, or operational writes.
  The 1.x releases remain read-only.

Every commit follows Conventional Commits: `type(scope): summary`, lowercase,
imperative, no trailing period, at most 72 characters. Use `feat` for additions,
`fix` for fixes and `!` for breaking changes. CI checks every published commit.
Release PRs must be **squash-merged** with their exact title,
`chore(release): v<VERSION>`, so that the tagged commit is the reviewed release
commit. Never move an existing tag.

### Automated preparation

`.github/workflows/release-please.yml` maintains one release PR from commits on
main. Release-please owns `VERSION`, its tracking manifest and the generated
changelog entries. `tools/scripts/prepare_release_pr.py` preserves matching
curated migration notes, synchronizes README/migration titles and skill versions,
then runs the existing manifest generators. CI rejects generated-file drift.
The legacy `bump_version.py` command is for reviewed maintenance/migration only;
do not run it in competition with an open automated release PR.

The workflow uses a pinned release-please action, Blacksmith runners and
`GITHUB_TOKEN`. Since that token does not trigger push/pull-request workflows,
the workflow explicitly dispatches `validate.yml` on the final release-PR head.
It never merges the PR, creates a tag, or publishes a release. Merging an
ordinary implementation PR may create/update the release PR, but cannot publish.

Before merging the release PR, review the changelog, migration guidance and
generated manifests. Preserve useful curated notes; generated commit summaries
are a starting point, not a substitute for release review.

### Explicit publication

After squash-merging the release PR:

1. Check out its exact commit, build the final export and inspect the ZIP.
2. Complete current judge calibration, the full evidence-fidelity matrix and
   manual semantic review for that exact candidate as described in
   `tools/tests/README.md`. Keep raw receipts in ignored results directories.
   This remains a human signoff; CI does not run credentialed model turns.
3. Obtain explicit approval for the commit, ZIP checksum and release tag.
4. Run the **Release** workflow manually on `main`, supplying the exact
   40-character release commit SHA, the reviewed ZIP's SHA-256, and the fidelity
   review confirmation. An unreviewed candidate cannot be published.
5. The prepare job verifies main ancestry, release commit subject, tracking
   manifest, dated metadata, static checks, publication scan and deterministic
   ZIP checksum. It uploads only the reviewed ZIP, checksum, inventory and notes.
6. Approve the `release` environment deployment. Its required maintainer
   reviewer and `main`-only deployment policy must be configured before use.
   Approval happens after preparation, and the publish job downloads that
   prepare job's exact artifact ID.
7. The publish job creates an annotated immutable tag and a GitHub Release with
   `rootly-v<VERSION>.zip`, its `.sha256`, and `release-inventory.json`.
   It uploads the existing prepared bytes, rather than rebuilding after approval.

The publisher is the only owner of tags and GitHub releases. Release-please runs
in PR-only mode; it does not create a competing release. No tag-push workflow is
needed, so the token's event-suppression behavior cannot skip asset publication.
The workflow does not submit to any marketplace.

A failed publication can resume when its existing tag still points at the same
approved commit and no GitHub Release exists. It refuses a different tag target
or an already published release. Repair partial asset uploads only after review;
do not delete/move tags or overwrite published assets to force a retry.

The release notes include curated/generated changelog entries, changed skills,
the previous-tag comparison (including the historical `v1.0`), install commands
and the archive checksum.

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
