#!/usr/bin/env python3
"""Check commit subjects against Conventional Commits, and release commits against the release format."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TYPES = ("feat", "fix", "docs", "refactor", "perf", "test", "build", "ci", "chore", "revert")
SUBJECT = re.compile(r"(?P<type>[a-z]+)(?:\((?P<scope>[a-z0-9-]+)\))?(?P<breaking>!)?: (?P<summary>.+)")
MAX_SUBJECT = 72


def subject_problems(subject):
    """Return the reasons a commit subject breaks the convention, or [] when it complies."""
    match = SUBJECT.fullmatch(subject)
    if match is None:
        return [f"{subject!r}: expected 'type(scope): summary', e.g. 'fix(on-call): ...'"]
    problems = []
    if match["type"] not in TYPES:
        problems.append(f"{subject!r}: unknown type {match['type']!r}; use one of {', '.join(TYPES)}")
    summary = match["summary"]
    if summary != summary.strip():
        problems.append(f"{subject!r}: summary has surrounding whitespace")
    if summary.endswith("."):
        problems.append(f"{subject!r}: summary ends with a period")
    if summary[:1].isupper() and not summary.split(" ", 1)[0].isupper():
        problems.append(f"{subject!r}: summary starts with a capital letter")
    if len(subject) > MAX_SUBJECT:
        problems.append(f"{subject!r}: subject is longer than {MAX_SUBJECT} characters")
    return problems


def release_subject(version):
    return f"chore(release): v{version}"


def commits(revisions, root=ROOT):
    """(sha, subject, body) for each non-merge commit in the revision range."""
    output = subprocess.check_output(["git", "log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e", revisions],
                                     cwd=root, text=True)
    entries = []
    for record in output.split("\x1e"):
        if record.strip():
            sha, subject, body = record.strip("\n").split("\x1f", 2)
            entries.append((sha, subject, body))
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revisions", nargs="?", default="HEAD^!",
                        help="git revision range to check (default: the last commit)")
    parser.add_argument("--release", metavar="TAG",
                        help="require the tagged commit's subject to be 'chore(release): TAG'")
    args = parser.parse_args()
    problems = []
    if args.release:
        subject = subprocess.check_output(["git", "log", "-1", "--format=%s", args.release], cwd=ROOT, text=True).strip()
        expected = release_subject(args.release.removeprefix("v"))
        if subject != expected:
            problems.append(f"{args.release}: release commit subject is {subject!r}, expected {expected!r}")
    else:
        for sha, subject, _ in commits(args.revisions):
            problems.extend(f"{sha[:12]} {problem}" for problem in subject_problems(subject))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("Commit messages follow the convention.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
