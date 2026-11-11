#!/usr/bin/env python3
"""Synchronize generated metadata after release-please updates VERSION/changelog."""

import argparse
import re
from pathlib import Path

import bump_version
import check_release_metadata as metadata

ROOT = Path(__file__).resolve().parents[2]


def replace_pattern(path, pattern, replacement):
    text, count = re.subn(pattern, replacement, path.read_text(), count=1, flags=re.M)
    if count != 1:
        raise ValueError(f"{path}: missing version field")
    path.write_text(text)


def prepare(root=ROOT):
    version = metadata.current_version(root)
    metadata.parse_version(version)
    changelog = root / "CHANGELOG.md"
    text = changelog.read_text()
    # Release-please emits linked SemVer headings. Retain our historical format
    # and preserve curated migration notes from the matching unreleased section.
    pattern = r"^## \[?(\d+\.\d+\.\d+)\]?(?:\([^\n]+\))? \((\d{4}-\d{2}-\d{2})\)$"
    text = re.sub(pattern, r"## \1 — \2", text, flags=re.M)
    sections = metadata.changelog_sections(text)
    if not sections or sections[0][0] != version or sections[0][1] == "unreleased":
        raise ValueError("Expected a dated release-please section matching VERSION")
    if len(sections) > 1 and sections[1][:2] == (version, "unreleased"):
        first, pending = sections[:2]
        matches = list(metadata.HEADING.finditer(text))
        end = matches[2].start() if len(matches) > 2 else len(text)
        combined = f"### Migration notes\n\n{pending[2]}\n\n{first[2]}"
        text = (text[:matches[0].start()] + f"## {version} — {first[1]}\n\n"
                + combined.strip() + "\n\n" + text[end:])
    changelog.write_text(text)
    replace_pattern(root / "README.md", r"^`\d+\.\d+(?:\.\d+)?`", f"`{version}`")
    replace_pattern(root / "docs/migration.md", r"^# Migration to \S+", f"# Migration to {version}")
    for skill in sorted((root / "skills").glob("*/SKILL.md")):
        replace_pattern(skill, r'^  version: "[^"]+"', f'  version: "{version}"')
    bump_version.regenerate()
    errors = metadata.problems(root, released=True)
    if errors:
        raise ValueError("\n".join(errors))
    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(f"Prepared release {prepare()}")
