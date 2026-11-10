#!/usr/bin/env python3
"""Fail if any file that git would track contains a private or credential marker.

This repository is public. Planning, telemetry, interview material and test
traces live elsewhere. The markers are the exporter's generic list plus the
local .private-markers file or CI environment. Only exact, reviewed example
lines are exempt from private-marker detection; credentials are never exempt.
"""

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

import export_release

ROOT = Path(__file__).resolve().parents[2]
# These exact source/test lines intentionally contain generic example markers.
# Never exempt a whole file or a credential match. Edits require explicit review.
INTENTIONAL_LINE_SHA256 = {
    "tools/scripts/export_release.py": {"b8589876d6efd2a44b70ff5bd7c0aa83fc0170be627099f22c2f04c2b1384ad1"},
    "tools/scripts/validate_skills.py": {"5219a10d8bd70778f6b06e76b276f5b86932f1f88523119768117c7f368ac2d7"},
    "tools/tests/static/test_package.py": {
        "a61552bce1fd7ec4be71d67c338fd9e89e5def2c11aa684a9d55ab02d42bcd6a",
        "5eff813c045204814c7d935c99fd851a144908908f98c89bba405122c9749943",
        "46c7040dccd7d0f45430e73332b156168ee4982293dc8cf41981daf7f5b24e61",
        "dd03ed5c89e32f801f3ea6511e3865372b27349f8d091527f86ab7d599269d9d",
    },
    "tools/tests/static/test_validation.py": {"59859360a40629d1b0914dd8cfd658112b31e4c5e3b418142d1f975eb650232f"},
}


def tracked_candidates(root=ROOT):
    output = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                                     cwd=root, text=True)
    return [name for name in output.split("\0") if name]


def findings(root=ROOT, names=None, require_private=False):
    private = export_release.private_pattern(require_private=require_private)
    problems = []
    for name in names if names is not None else tracked_candidates(root):
        path = root / name
        if private.search(name):
            problems.append((name, "private path"))
            continue
        if path.is_symlink() or not path.is_file():
            problems.append((name, "symlink or missing/non-file candidate"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            problems.append((name, "non-UTF-8 or unreadable file"))
            continue
        if "\x00" in text:
            problems.append((name, "binary file"))
            continue
        lines = text.splitlines()
        for match in export_release.SECRET.finditer(text):
            problems.append((name, f"credential marker on line {text.count(chr(10), 0, match.start()) + 1}"))
        for match in private.finditer(text):
            number = text.count("\n", 0, match.start()) + 1
            end_number = text.count("\n", 0, max(match.start(), match.end() - 1)) + 1
            if (number == end_number and number <= len(lines)
                    and hashlib.sha256(lines[number - 1].encode()).hexdigest() in INTENTIONAL_LINE_SHA256.get(name, set())):
                continue
            problem = (name, f"private marker on line {number}")
            if problem not in problems:
                problems.append(problem)
    return problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-private-markers", action="store_true")
    args = parser.parse_args()
    try:
        problems = findings(require_private=args.require_private_markers)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
    for name, marker in problems:
        print(f"{name}: {marker}")
    print(f"{len(problems)} private marker(s) in files git would track" if problems
          else "No private markers in files git would track.")
    sys.exit(1 if problems else 0)
