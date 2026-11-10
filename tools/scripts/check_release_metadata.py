#!/usr/bin/env python3
"""Check that VERSION, CHANGELOG.md and the user-facing docs name one version."""

import argparse
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)")
HEADING = re.compile(r"^## (?P<version>\S+) — (?P<state>unreleased|\d{4}-\d{2}-\d{2})$", re.M)


def parse_version(text):
    """Return a sortable (major, minor) tuple; versions are MAJOR.MINOR, e.g. 1.0, 1.1, 2.0."""
    match = VERSION_PATTERN.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"Invalid version {text.strip()!r}; expected MAJOR.MINOR, e.g. 1.0")
    major, minor = match.groups()
    return (int(major), int(minor))


def current_version(root=ROOT):
    return (root / "VERSION").read_text().strip()


def changelog_sections(text):
    """Return [(version, state, body)] for every well-formed '## ' heading, in order."""
    matches = list(HEADING.finditer(text))
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match["version"], match["state"], text[match.end():end].strip()))
    return sections


def notes(root=ROOT):
    """Release notes: the body of the top changelog section."""
    sections = changelog_sections((root / "CHANGELOG.md").read_text())
    if not sections:
        raise ValueError("CHANGELOG.md: no version section")
    return sections[0][2]


def problems(root=ROOT, released=False, tag=None):
    errors = []
    version = current_version(root)
    try:
        parse_version(version)
    except ValueError as exc:
        return [str(exc)]
    changelog = (root / "CHANGELOG.md").read_text()
    sections = changelog_sections(changelog)
    if len(re.findall(r"^## ", changelog, re.M)) != len(sections):
        errors.append("CHANGELOG.md: every '## ' heading must read "
                      "'## VERSION — unreleased' or '## VERSION — YYYY-MM-DD'")
    if not sections:
        errors.append("CHANGELOG.md: no version section")
    else:
        top_version, state, body = sections[0]
        if top_version != version:
            errors.append(f"CHANGELOG.md: top section is {top_version}, VERSION is {version}")
        if state != "unreleased":
            try:
                datetime.date.fromisoformat(state)
            except ValueError:
                errors.append(f"CHANGELOG.md: invalid release date {state}")
        if released and state == "unreleased":
            errors.append(f"CHANGELOG.md: {version} is still marked unreleased")
        if released and not re.search(r"^- \S", body, re.M):
            errors.append(f"CHANGELOG.md: {version} has no entries")
        for other_version, other_state, _ in sections[1:]:
            if other_state == "unreleased":
                errors.append(f"CHANGELOG.md: {other_version} is unreleased but not the top section")
        versions = [section[0] for section in sections]
        if len(versions) != len(set(versions)):
            errors.append("CHANGELOG.md: duplicate version section")
    if f"`{version}`" not in (root / "README.md").read_text():
        errors.append(f"README.md: status line does not name `{version}`")
    migration_title = (root / "docs/migration.md").read_text().splitlines()[0]
    if migration_title != f"# Migration to {version}":
        errors.append(f"docs/migration.md: title is {migration_title!r}, expected '# Migration to {version}'")
    if tag is not None and tag != f"v{version}":
        errors.append(f"Tag {tag} does not match v{version}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--released", action="store_true",
                        help="require a dated top changelog section with entries")
    parser.add_argument("--tag", help="git tag that must equal v<VERSION>")
    parser.add_argument("--notes", action="store_true",
                        help="print the top changelog section body instead of checking")
    args = parser.parse_args()
    if args.notes:
        print(notes())
        return 0
    errors = problems(released=args.released, tag=args.tag)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Release metadata agrees on {current_version()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
