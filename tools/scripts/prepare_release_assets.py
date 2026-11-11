#!/usr/bin/env python3
"""Assemble only the exact ZIP and inventory approved for a release."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import check_release_metadata as metadata


def assemble(package, tag, expected, destination):
    if not tag.startswith("v"):
        raise ValueError("Expected a version tag")
    metadata.parse_version(tag[1:])
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Provide the SHA-256 of the reviewed ZIP")
    archive = Path(package["archive"])
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError("Candidate ZIP differs from the reviewed artifact")
    destination.mkdir()
    name = f"rootly-{tag}.zip"
    shutil.copyfile(archive, destination / name)
    shutil.copyfile(Path(package["directory"]) / "release-inventory.json",
                    destination / "release-inventory.json")
    (destination / (name + ".sha256")).write_text(f"{expected}  {name}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("expected_sha256")
    args = parser.parse_args()
    assemble(json.loads(Path("export.json").read_text()), args.tag,
             args.expected_sha256, Path("release"))
