#!/usr/bin/env python3
"""Move every version reference (VERSION, changelog, docs, skill frontmatter, manifests)
to a new version, or date the current one as released."""

import argparse
import datetime
import re
import sys
from pathlib import Path

import build_package
import check_release_metadata as metadata

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError(f"{path.name}: expected exactly one occurrence of {old!r}")
    path.write_text(text.replace(old, new))


def regenerate():
    for path, content in build_package.generated_files():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def bump(new, root=ROOT, allow_downgrade=False):
    """Set VERSION to `new` and carry it into the changelog, docs and manifests.

    A version that does not follow the current one is refused unless
    `allow_downgrade` is set; that is only legitimate before the first tag.
    """
    current = metadata.current_version(root)
    legacy = bool(re.fullmatch(r"\d+\.\d+", current))
    normalized = current + ".0" if legacy else current
    ordered = metadata.parse_version(new) > metadata.parse_version(normalized)
    migration = legacy and new == normalized
    if not ordered and not migration and not allow_downgrade:
        raise ValueError(f"{new} does not follow {current}")
    if new == current:
        raise ValueError(f"VERSION is already {current}")
    changelog = root / "CHANGELOG.md"
    sections = metadata.changelog_sections(changelog.read_text())
    if not sections or sections[0][0] != current:
        raise ValueError(f"CHANGELOG.md: top section must be {current}")
    state = sections[0][1]
    if state == "unreleased":
        replace_once(changelog, f"## {current} — unreleased", f"## {new} — unreleased")
    else:
        replace_once(changelog, f"## {current} — {state}",
                     f"## {new} — unreleased\n\n## {current} — {state}")
    replace_once(root / "README.md", f"`{current}`", f"`{new}`")
    for skill in sorted((root / "skills").glob("*/SKILL.md")):
        replace_once(skill, f'version: "{current}"', f'version: "{new}"')
    replace_once(root / "docs/migration.md", f"# Migration to {current}", f"# Migration to {new}")
    (root / "VERSION").write_text(new + "\n")
    regenerate()
    errors = metadata.problems(root)
    if errors:
        raise ValueError("\n".join(errors))
    return new


def release(root=ROOT, today=None):
    """Date the current unreleased changelog section; return the tag to create."""
    current = metadata.current_version(root)
    sections = metadata.changelog_sections((root / "CHANGELOG.md").read_text())
    if not sections or sections[0][0] != current or sections[0][1] != "unreleased":
        raise ValueError(f"CHANGELOG.md: top section must be '## {current} — unreleased'")
    today = today or datetime.datetime.now(datetime.UTC).date().isoformat()
    replace_once(root / "CHANGELOG.md", f"## {current} — unreleased", f"## {current} — {today}")
    errors = metadata.problems(root, released=True)
    if errors:
        raise ValueError("\n".join(errors))
    return f"v{current}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("version", nargs="?", help="new version, e.g. 1.1.0")
    group.add_argument("--release", action="store_true",
                       help="date the current version's changelog section as released today")
    parser.add_argument("--allow-downgrade", action="store_true",
                        help="accept a version that does not follow the current one; "
                             "only before the first release tag exists")
    args = parser.parse_args()
    try:
        if args.release:
            tag = release()
            print(f"CHANGELOG.md now dates {tag[1:]}. Run the release checks, then:")
            print(f"  git commit -am 'chore(release): {tag}'")
            print(f"  git tag -a {tag} -m {tag} && git push origin main {tag}")
        else:
            version = bump(args.version, allow_downgrade=args.allow_downgrade)
            print(f"VERSION is now {version}; manifests regenerated.")
            print("Fill in the CHANGELOG.md entries for this version, then run --release.")
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
