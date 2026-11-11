#!/usr/bin/env python3
"""Validate an explicitly selected release commit without publishing anything."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import check_release_metadata as metadata

ROOT = Path(__file__).resolve().parents[2]


def git(*args, root=ROOT):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def verify(sha, root=ROOT):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Select an exact 40-character commit SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", sha, "origin/main"],
                   cwd=root, check=True, capture_output=True)
    version = git("show", f"{sha}:VERSION", root=root)
    metadata.parse_version(version)
    if git("log", "-1", "--format=%s", sha, root=root) != f"chore(release): v{version}":
        raise ValueError("Candidate must be the squash-merged release PR commit")
    manifest = json.loads(git("show", f"{sha}:.release-please-manifest.json", root=root))
    if manifest.get(".") != version:
        raise ValueError("Release manifest must agree with VERSION")
    tag = f"v{version}"
    existing = subprocess.run(["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
                              cwd=root, capture_output=True, text=True)
    if existing.returncode == 0 and existing.stdout.strip() != sha:
        raise ValueError("Existing tag targets a different commit; tags are immutable")
    return {"sha": sha, "version": version, "tag": tag}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sha")
    args = parser.parse_args()
    result = verify(args.sha)
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            output.write("".join(f"{key}={value}\n" for key, value in result.items()))
    print(json.dumps(result))
