#!/usr/bin/env python3
"""Build an exact-source Microsoft 365 ZIP; never authenticate or submit."""

import argparse
import hashlib
import io
import json
import re
import struct
import zipfile
from datetime import date
from pathlib import Path

import check_release_metadata as metadata
import microsoft_manifest
from prepare_marketplace_bundle import encoded, read_package, verify_source
from public_assets import reviewed_binary

ROOT = Path(__file__).resolve().parents[2]


def package_files(files, version):
    """Select the approved incident workflows and verify adapter/icon drift."""
    manifest_bytes = files["adapters/microsoft/manifest.json"]
    if json.loads(manifest_bytes) != microsoft_manifest.manifest(version):
        raise ValueError("Microsoft manifest differs from generated metadata")
    selected = {"manifest.json": manifest_bytes}
    for name, size in (("color.png", 192), ("outline.png", 32)):
        source = f"assets/microsoft/{name}"
        content = files[source]
        if not reviewed_binary(source, content):
            raise ValueError("Unreviewed Microsoft icon")
        if (content[:8] != b"\x89PNG\r\n\x1a\n"
                or struct.unpack(">II", content[16:24]) != (size, size)):
            raise ValueError("Unexpected Microsoft icon dimensions")
        selected[name] = content
    for skill in microsoft_manifest.SKILLS:
        prefix = f"skills/{skill}/"
        if prefix + "SKILL.md" not in files:
            raise ValueError(f"Missing Microsoft skill: {skill}")
        selected.update((name, content) for name, content in files.items()
                        if name.startswith(prefix))
    return selected


def archive_bytes(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, content)
    return stream.getvalue()


def prepare(export, tag, candidate, output, *, preview=False, expected=None, root=ROOT):
    if not re.fullmatch(r"[0-9a-f]{40}", candidate):
        raise ValueError("Require the exact 40-character candidate SHA")
    _, files, _, _, _ = read_package(export, tag)
    verify_source(files, candidate, root)
    if not preview:
        sections = metadata.changelog_sections(files["CHANGELOG.md"].decode())
        if not sections or sections[0][0] != tag[1:] or sections[0][1] == "unreleased":
            raise ValueError("Require dated release metadata; use --preview")
        date.fromisoformat(sections[0][1])
        if not expected or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Require the reviewed Microsoft ZIP SHA-256")
    selected = package_files(files, tag[1:])
    archive = archive_bytes(selected)
    digest = hashlib.sha256(archive).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError("Microsoft ZIP differs from the reviewed artifact")
    suffix = f"preview-{candidate[:12]}" if preview else tag
    name = f"rootly-microsoft-{suffix}.zip"
    inventory = {
        "stage": "preview" if preview else "release-preparation",
        "candidate_sha": candidate, "version": tag[1:], "app_id": microsoft_manifest.APP_ID,
        "archive": name, "sha256": digest, "source_archive_sha256": export["sha256"],
        "files": {name: hashlib.sha256(content).hexdigest()
                  for name, content in sorted(selected.items())},
        "provider_validation": "pending", "submitted": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / name).write_bytes(archive)
    (output / (name + ".sha256")).write_text(f"{digest}  {name}\n")
    (output / (name.removesuffix(".zip") + "-inventory.json")).write_bytes(encoded(inventory))
    (output / "README.md").write_text(
        ("PREVIEW — NOT A RELEASE. Do not submit.\n" if preview
         else "RELEASE PREPARATION — NOT SUBMITTED.\n")
        + f"Candidate: {candidate}\nMicrosoft ZIP: {name}\nSHA-256: {digest}\n"
        + "Validate the exact ZIP in Microsoft Developer Portal and test in Cowork.\n"
        + "Review permissions, reviewer access and certification instructions before submission.\n"
        + "Enter credentials only in the provider portal, never in this artifact.\n"
        + "Public submission is manual in Partner Center after explicit authorization.\n"
    )
    return inventory, output / name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    inventory, archive = prepare(
        json.loads(args.export.read_text()), args.tag, args.candidate, args.output,
        preview=args.preview, expected=args.expected_sha256,
    )
    print(json.dumps({"archive": str(archive), "sha256": inventory["sha256"]}))


if __name__ == "__main__":
    main()
