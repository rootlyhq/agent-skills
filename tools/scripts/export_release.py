#!/usr/bin/env python3
"""Export an allowlisted, deterministic release without publishing or git history."""

import argparse
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path

import build_package
from public_assets import reviewed_binary

ROOT = Path(__file__).resolve().parents[2]
TOP_FILES = (
    "VERSION", "README.md", "LICENSE", "NOTICE", "CHANGELOG.md", "plugin.json", "mcp.json", ".mcp.json",
    ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
    ".cursor-plugin/plugin.json",
    ".devin-plugin/plugin.json", ".agents/plugins/marketplace.json",
    "assets/logo.svg", "assets/microsoft/color.png", "assets/microsoft/outline.png",
    "docs/microsoft-copilot.md",
    "docs/install.md", "docs/safety.md", "docs/migration.md", "docs/architecture.md",
)
TREES = ("skills", "adapters")
GENERIC_PRIVATE = r"/Users/|/home/[^/\s]+/|practitioner-workbook|IMPLEMENTATION_PLAN|agent-skills-context"
def private_pattern(require_private=False):
    """Generic markers plus optional, untracked local ones (one regex per line).

    Names of people and internal tools live only in the ignored .private-markers
    file, so this public source never lists them.
    """
    extra = []
    markers = ROOT / ".private-markers"
    if markers.is_file():
        extra = [line.strip() for line in markers.read_text().splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
    extra.extend(line.strip() for line in os.environ.get("ROOTLY_SKILLS_PRIVATE_MARKERS", "").splitlines()
                 if line.strip() and not line.lstrip().startswith("#"))
    if require_private and not extra:
        raise ValueError("Private markers are required; configure the ignored local file or CI secret.")
    try:
        return re.compile("|".join([GENERIC_PRIVATE, *extra]), re.IGNORECASE)
    except re.error:
        raise ValueError("Invalid private-marker expression (value withheld).") from None

SECRET = re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_\-]{20,}")


def release_files():
    for path, content in build_package.generated_files():
        if not path.is_file() or path.read_text() != content:
            raise ValueError(f"Generated file is stale: {path.relative_to(ROOT)}")
    paths = [ROOT / name for name in TOP_FILES]
    for tree in TREES:
        tree_root = ROOT / tree
        if tree_root.is_symlink() or not tree_root.is_dir():
            raise ValueError(f"Missing or symlinked release tree: {tree}")
        for path in tree_root.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Symlink in release tree: {path}")
            if path.is_file():
                paths.append(path)
    result = {}
    private = private_pattern()
    for path in sorted(paths):
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError(f"Symlink or escaping release path: {path}")
        if any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(ROOT)):
            raise ValueError(f"Symlinked release parent: {path}")
        if not path.is_file():
            raise ValueError(f"Required release file missing: {path}")
        relative = path.relative_to(ROOT).as_posix()
        content = path.read_bytes()
        if reviewed_binary(relative, content):
            if private.search(relative):
                raise ValueError(f"Private marker in asset path: {relative}")
            result[relative] = content
            continue
        if path.suffix not in (".md", ".json", ".yaml", ".toml", ".svg") and relative not in ("VERSION", "LICENSE", "NOTICE"):
            raise ValueError(f"Unexpected release file type: {relative}")
        text = content.decode("utf-8")
        if private.search(relative) or private.search(text) or SECRET.search(text):
            raise ValueError(f"Private/source/credential marker found in {relative}")
        result[relative] = content
    return result


def export(output):
    files = release_files()
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    inventory = (json.dumps(hashes, sort_keys=True, indent=2) + "\n").encode()
    digest = hashlib.sha256(inventory).hexdigest()
    version = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"[0-9A-Za-z.\-]+", version):
        raise ValueError("Unsafe VERSION")
    name = f"rootly-{version}-{digest[:12]}"
    destination = output / name
    if destination.is_symlink():
        raise ValueError("Release destination cannot be a symlink")
    expected = {**files, "release-inventory.json": inventory}
    if destination.exists():
        entries = list(destination.rglob("*"))
        if any(p.is_symlink() for p in entries):
            raise ValueError("Existing release tree contains a symlink")
        actual = {p.relative_to(destination).as_posix(): p for p in entries if p.is_file()}
        if set(actual) != set(expected) or any(p.is_symlink() or p.read_bytes() != expected[n] for n, p in actual.items()):
            raise ValueError("Existing release tree differs; refusing to overwrite it")
    else:
        destination.mkdir(parents=True)
        for relative, content in expected.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    archive = output / (name + ".zip")
    if not archive.exists():
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            for relative, content in sorted(expected.items()):
                info = zipfile.ZipInfo(f"{name}/{relative}", (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, content)
    else:
        if archive.is_symlink():
            raise ValueError("Release archive cannot be a symlink")
        with zipfile.ZipFile(archive) as bundle:
            names = {f"{name}/{n}" for n in expected}
            if set(bundle.namelist()) != names or len(bundle.namelist()) != len(names):
                raise ValueError("Existing archive inventory differs")
            if any(bundle.read(f"{name}/{n}") != content for n, content in expected.items()):
                raise ValueError("Existing archive content differs")
    return {
        "directory": str(destination), "archive": str(archive), "file_count": len(expected),
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    print(json.dumps(export(args.output.resolve()), indent=2))
