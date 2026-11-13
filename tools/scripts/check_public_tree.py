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
from public_assets import reviewed_binary

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


def content_findings(name, content, private):
    """Inspect bytes from either the worktree or a Git blob without exposing values."""
    if private.search(name):
        return [(name, "private path")]
    try:
        if reviewed_binary(name, content):
            return []
    except ValueError:
        return [(name, "binary branding asset differs from reviewed checksum")]
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return [(name, "non-UTF-8 or unreadable file")]
    if "\x00" in text:
        return [(name, "binary file")]
    problems, lines = [], text.splitlines()
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


def git_findings(root=ROOT, *, staged=False, revision_range=None, require_private=False):
    """Scan the index or every committed tree in a range, including removed blobs."""
    if staged == (revision_range is not None):
        raise ValueError("Choose exactly one Git scan mode")
    private = export_release.private_pattern(require_private=require_private)
    def git(*args, input=None):
        return subprocess.run(["git", "--no-replace-objects", *args], cwd=root, input=input, capture_output=True,
                              check=True).stdout
    if staged:
        snapshots = [("index", git("ls-files", "--stage", "-z"))]
    else:
        commits = git("rev-list", "--end-of-options", revision_range).decode("ascii").splitlines()
        snapshots = ((commit, git("ls-tree", "-rz", "--full-tree", commit)) for commit in commits)
    problems, seen = [], set()
    for scope, tree in snapshots:
        entries = []
        for entry in tree.split(b"\0"):
            if not entry:
                continue
            metadata, raw_name = entry.split(b"\t", 1)
            mode, middle, last = metadata.decode("ascii").split()
            name = raw_name.decode("utf-8")
            oid = middle if staged else last
            if staged and last != "0":
                problems.append((name, "unmerged index entry"))
                continue
            key = (name, mode, oid)
            if key in seen:
                continue
            seen.add(key)
            if mode not in ("100644", "100755"):
                problems.append((f"{scope}:{name}", "symlink or non-file Git entry"))
                continue
            entries.append((name, oid))
        # One batch per tree avoids launching a process per blob. Parse by byte
        # count so binary contents cannot corrupt record boundaries.
        blobs = git("cat-file", "--batch", input="".join(oid + "\n" for _, oid in entries).encode())
        offset = 0
        for name, oid in entries:
            end = blobs.index(b"\n", offset)
            header = blobs[offset:end].decode("ascii").split()
            if len(header) != 3 or header[:2] != [oid, "blob"]:
                raise ValueError("Unreadable Git blob")
            size = int(header[2])
            content = blobs[end + 1:end + 1 + size]
            if len(content) != size or blobs[end + 1 + size:end + 2 + size] != b"\n":
                raise ValueError("Truncated Git blob")
            offset = end + 2 + size
            problems.extend((f"{scope}:{path}", reason)
                            for path, reason in content_findings(name, content, private))
    return problems


def findings(root=ROOT, names=None, require_private=False):
    private = export_release.private_pattern(require_private=require_private)
    problems = []
    for name in names if names is not None else tracked_candidates(root):
        path = root / name
        if path.is_symlink() or not path.is_file():
            problems.append((name, "symlink or missing/non-file candidate"))
            continue
        try:
            content = path.read_bytes()
        except OSError:
            problems.append((name, "non-UTF-8 or unreadable file"))
            continue
        problems.extend(content_findings(name, content, private))
    return problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-private-markers", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="Scan exact index blobs, independent of working files")
    mode.add_argument("--range", dest="revision_range", help="Scan every committed tree in a Git revision range")
    args = parser.parse_args()
    try:
        if args.staged or args.revision_range is not None:
            problems = git_findings(staged=args.staged, revision_range=args.revision_range,
                                    require_private=args.require_private_markers)
        else:
            problems = findings(require_private=args.require_private_markers)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print("Publication scan failed (" + type(error).__name__
              + "); check the Git range, index and private-marker configuration.", file=sys.stderr)
        raise SystemExit(1)
    for name, marker in problems:
        print(f"{name}: {marker}")
    print(f"{len(problems)} publication finding(s)" if problems else "No publication findings.")
    sys.exit(1 if problems else 0)
