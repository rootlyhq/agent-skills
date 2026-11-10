#!/usr/bin/env python3
"""Compose GitHub Release notes: changelog entries, what changed, install, checksum."""

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

import check_release_metadata as metadata

ROOT = Path(__file__).resolve().parents[2]
REPO = "rootlyhq/agent-skills"


def previous_tag(tag, root=ROOT):
    """The nearest earlier release tag reachable from `tag`, or None for the first release."""
    result = subprocess.run(["git", "describe", "--tags", "--abbrev=0", "--match", "v*", f"{tag}^"],
                            cwd=root, capture_output=True, text=True)
    return result.stdout.strip() or None


def changed_paths(tag, previous, root=ROOT):
    if previous is None:
        return None
    output = subprocess.check_output(["git", "diff", "--name-only", f"{previous}..{tag}"], cwd=root, text=True)
    return [line for line in output.splitlines() if line]


def changed_summary(paths):
    if paths is None:
        return "Skills: all seven (first release)."
    skills = sorted({p.split("/")[1] for p in paths if p.startswith("skills/") and p.count("/") >= 2})
    areas = sorted({p.split("/")[0] for p in paths if not p.startswith("skills/")})
    lines = ["Skills: " + (", ".join(skills) if skills else "unchanged")]
    if areas:
        lines.append("Also: " + ", ".join(areas))
    return "\n".join(lines)


def compose(tag, archive, previous, paths, root=ROOT):
    version = metadata.current_version(root)
    if tag != f"v{version}":
        raise ValueError(f"Tag {tag} does not match v{version}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    lines = ["## What's new", "", metadata.notes(root), ""]
    lines += [f"## Changed since {previous}" if previous else "## Changed", "", changed_summary(paths)]
    if previous:
        lines += ["", f"Full diff: https://github.com/{REPO}/compare/{previous}...{tag}"]
    lines += [
        "", "## Install", "",
        "```sh",
        f"claude plugin marketplace add {REPO}",
        "claude plugin install rootly@rootly-agent-skills --scope local",
        "```", "",
        f"Codex: `codex plugin marketplace add {REPO}`, then `codex plugin add rootly@rootly-agent-skills`.",
        f"Devin: `devin plugins install {REPO}`. Cursor: install **Rootly** from the marketplace.",
        "", "## Package", "",
        f"`{archive.name}` · SHA-256 `{digest}`", "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    try:
        previous = previous_tag(args.tag)
        print(compose(args.tag, args.archive, previous, changed_paths(args.tag, previous)))
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
