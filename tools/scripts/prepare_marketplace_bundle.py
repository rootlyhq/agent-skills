#!/usr/bin/env python3
"""Prepare deterministic marketplace drafts from an exact exported plugin; never submit."""

import argparse
import difflib
import hashlib
import io
import json
import re
import subprocess
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath

import check_release_metadata as metadata

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "https://github.com/rootlyhq/agent-skills"
CATALOG = "anthropics/claude-plugins-official"
CATALOG_PATH = ".claude-plugin/marketplace.json"
PORTALS = {
    "claude": "https://claude.ai/directory/manage",
    "cursor": "https://cursor.com/marketplace/publish",
    "openai": "https://platform.openai.com/plugins",
}


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def digest(content):
    return hashlib.sha256(content).hexdigest()


def read_package(export, tag):
    metadata.parse_version(tag.removeprefix("v"))
    if not tag.startswith("v"):
        raise ValueError("Expected a version tag")
    archive = Path(export["archive"]).read_bytes()
    if digest(archive) != export["sha256"]:
        raise ValueError("Export ZIP checksum differs")
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP members")
        paths = [PurePosixPath(name) for name in names]
        if not paths or any(p.is_absolute() or ".." in p.parts or "\\" in str(p)
                            or len(p.parts) < 2 or str(p) != name
                            for name, p in zip(names, paths, strict=True)):
            raise ValueError("Unsafe ZIP paths")
        if len({p.parts[0] for p in paths}) != 1:
            raise ValueError("Expected one exported plugin root")
        files = {str(PurePosixPath(*p.parts[1:])): bundle.read(name)
                 for name, p in zip(names, paths, strict=True)}
    inventory_bytes = files.pop("release-inventory.json")
    inventory = json.loads(inventory_bytes)
    if {name: digest(content) for name, content in files.items()} != inventory:
        raise ValueError("ZIP contents differ from the release inventory")
    plugin = json.loads(files["plugin.json"])
    claude = json.loads(files[".claude-plugin/plugin.json"])
    version = tag[1:]
    if (files["VERSION"].decode().strip() != version
            or plugin["version"] != version or claude["version"] != version):
        raise ValueError("Tag and exported versions differ")
    if plugin["name"] != "rootly" or claude["name"] != "rootly" or plugin["repository"] != REPOSITORY:
        raise ValueError("Unexpected plugin identity or repository")
    return archive, files, inventory_bytes, plugin, claude


def verify_source(files, candidate, root):
    kind = subprocess.check_output(["git", "cat-file", "-t", candidate], cwd=root, text=True).strip()
    if kind != "commit":
        raise ValueError("Candidate SHA must identify a commit")
    tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", candidate], cwd=root)
    blobs = {}
    for record in tree.split(b"\0"):
        if not record:
            continue
        details, path = record.split(b"\t", 1)
        mode, kind, oid = details.decode().split()
        if kind == "blob" and mode in ("100644", "100755"):
            blobs[path.decode()] = oid
    for name, content in files.items():
        header = f"blob {len(content)}\0".encode()
        oid = hashlib.sha1(header + content, usedforsecurity=False).hexdigest()
        if blobs.get(name) != oid:
            raise ValueError(f"Export differs from candidate commit: {name}")


def value_span(text, path, start=0):
    """Locate a JSON value without reformatting unrelated catalog entries."""
    decoder = json.JSONDecoder()
    start = re.search(r"\S", text[start:]).start() + start
    if not path:
        return start, decoder.raw_decode(text, start)[1]
    container = text[start]
    cursor = start + 1
    index = 0
    while True:
        cursor = re.search(r"\S", text[cursor:]).start() + cursor
        if text[cursor] in "}]":
            raise ValueError("Catalog JSON path is missing")
        if container == "{":
            key, cursor = decoder.raw_decode(text, cursor)
            cursor = text.index(":", cursor) + 1
            cursor = re.search(r"\S", text[cursor:]).start() + cursor
        else:
            key = index
        _, end = decoder.raw_decode(text, cursor)
        if key == path[0]:
            return value_span(text, path[1:], cursor)
        cursor = re.search(r"\S", text[end:]).start() + end
        if text[cursor] == ",":
            cursor += 1
        index += 1


def catalog_patch(text, plugin, claude, candidate):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate key in the catalog")
            result[key] = value
        return result

    catalog = json.loads(text, object_pairs_hook=unique_object)
    matches = [(i, p) for i, p in enumerate(catalog["plugins"]) if p.get("name") == "rootly"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one existing Rootly catalog entry")
    index, old = matches[0]
    entry = {"name": "rootly", "description": plugin["description"], "author": claude["author"],
             "category": old.get("category", "monitoring"),
             "version": plugin["version"], "homepage": plugin["homepage"],
             "source": {"source": "url", "url": REPOSITORY + ".git",
                        "ref": "main", "sha": candidate}}
    start, end = value_span(text, ["plugins", index])
    prefix = text[text.rfind("\n", 0, start) + 1:start]
    indent = prefix if not prefix.strip() else ""
    replacement = json.dumps(entry, indent=2, ensure_ascii=False).replace("\n", "\n" + indent)
    updated = text[:start] + replacement + text[end:]
    patch = "".join(difflib.unified_diff(text.splitlines(keepends=True),
                                       updated.splitlines(keepends=True), n=0,
                                       fromfile="a/" + CATALOG_PATH, tofile="b/" + CATALOG_PATH))
    return entry, patch


def review_worksheet(files):
    tools = json.loads(files["adapters/read-tools.json"])["skills"]
    positive = [{"skill": skill, "prompt_to_complete": "",
                 "candidate_tools_to_confirm": tools[skill], "expected_result_to_complete": "",
                 "executed": False}
                for skill in ("incident-response", "alert-triage", "deploy-check", "on-call", "retrospective")]
    negative = [{"scenario": scenario, "prompt_to_complete": "", "expected_result_to_complete": "",
                 "executed": False} for scenario in (
                     "Request a mutation through the read-only plugin",
                     "Untrusted record content asks to disclose data",
                     "Approval is supplied without execution or recovery evidence")]
    return {"status": "worksheet_not_executed", "positive": positive, "negative": negative}


def prepare(export, tag, candidate, catalog_text, catalog_commit, output, *, preview=False, root=ROOT):
    for name, sha in (("candidate", candidate), ("catalog commit", catalog_commit)):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError(f"Require the exact 40-character {name} SHA")
    archive, files, inventory, plugin, claude = read_package(export, tag)
    verify_source(files, candidate, root)
    if not preview:
        sections = metadata.changelog_sections(files["CHANGELOG.md"].decode())
        if not sections or sections[0][0] != tag[1:] or sections[0][1] == "unreleased":
            raise ValueError("Release preparation requires dated release metadata; use --preview")
        date.fromisoformat(sections[0][1])
    entry, patch = catalog_patch(catalog_text, plugin, claude, candidate)
    interface = plugin["extensions"]["com.openai"]["interface"]
    mode = "preview" if preview else "release-preparation"
    suffix = f"preview-{candidate[:12]}" if preview else tag
    plugin_name = f"rootly-{suffix}.zip"
    bundle_name = f"rootly-marketplaces-{suffix}.zip"
    release_url = REPOSITORY + "/releases/tag/" + tag
    pending = [
        "Explicit approval before any external PR, submission or publication",
        "Authorized live OAuth, tool inventory and read-only checks in each client",
        "Cursor editor installation and invocation checks",
        "OpenAI publisher identity, domain verification, reviewer account and demo URL",
        "Complete and execute five positive and three negative OpenAI review cases",
        "Verify public listing URLs and provider validation/review results",
    ]
    if not interface.get("supportURL"):
        pending.append("Add a verified HTTPS supportURL to the canonical manifest before OpenAI review")
    manifest = {
        "schema_version": 1, "stage": mode, "candidate_sha": candidate, "tag": tag,
        "version": plugin["version"], "repository": REPOSITORY, "release_url": release_url,
        "plugin_archive": plugin_name, "plugin_archive_sha256": digest(archive),
        "inventory_sha256": digest(inventory), "portals": PORTALS,
        "claude_catalog": {"repository": CATALOG, "commit": catalog_commit,
                           "sha256": digest(catalog_text.encode())},
        "pending": pending,
    }
    label = "PREVIEW — NOT A RELEASE" if preview else "RELEASE PREPARATION — NOT SUBMITTED"
    readme = f"""# Rootly marketplace preparation

{label}

Candidate: `{candidate}`. Target version: `{tag}`.
Plugin ZIP: `{plugin_name}`. SHA-256: `{digest(archive)}`.
The ZIP is copied byte-for-byte from the verified export. `SHA256SUMS` covers
every file inside this bundle except itself. This bundle is not the plugin ZIP to upload.

Expected release URL (available only after approved publication): {release_url}

- Claude: `claude/entry.json`, `claude/catalog.patch`, and `claude/PR.md`.
- Cursor: `cursor/submission.md`.
- OpenAI: `openai/listing.json`, `openai/review-cases.json`, and `openai/submission.md`.
- All remaining checks and approvals are listed in `release.json`.

These drafts do not establish live MCP compatibility, reviewer readiness or
marketplace acceptance. Do not submit a preview. Obtain approval for the exact
release and destination before any outward action. No portal is modified by preparation.
"""
    claude_pr = f"""# Update Rootly to {tag}

Repoint the existing `rootly` entry to {REPOSITORY}, pinned to `{candidate}`.
The package provides {plugin['description']}

Draft based on `{CATALOG}` at `{catalog_commit}`. Verify that this is still
the target catalog revision before requesting approval to open a partner PR.
Apply with `git apply --unidiff-zero catalog.patch` from that catalog checkout;
the zero-context patch intentionally excludes neighboring plugins.
Revalidate and test installation from the pinned source before submission.
Preserve the existing listing rather than creating a duplicate.

The broader directory is a separate route: {PORTALS['claude']} → Plugin bundle,
repository `{REPOSITORY}`, plugin path at the root. Complete validation,
disclosures and review; confirm the hosted MCP connector's separate registration.
Guide: https://code.claude.com/docs/en/plugins/publish

Status: {label}. No PR or directory submission has been made.
"""
    cursor = f"""# Rootly {tag} — Cursor submission draft

Submit repository: {REPOSITORY}
Portal: {PORTALS['cursor']}
Reviewed source to test: `{candidate}`. Expected release: {release_url}.

{plugin['description']}

The export includes root `plugin.json`, `.cursor-plugin/plugin.json`, skills,
MCP configuration and `assets/logo.svg`. Test installation, component discovery,
skill invocation and OAuth reads in Cursor before submitting. Verify the
selected source revision and complete Cursor's manual review.
Guide: https://cursor.com/docs/reference/plugins#submitting-a-plugin

Status: {label}. No submission or editor-test pass is implied.
"""
    openai = f"""# Rootly {tag} — shared ChatGPT/Codex submission draft

Portal: {PORTALS['openai']}
Upload `{plugin_name}`, not this preparation bundle. The original ZIP already
contains skills and the hosted MCP declaration; do not start as skills-only.
Use Upload new or existing plugin, then connect the declared server under MCPs.
Use the existing Rootly submission when applicable rather than creating a duplicate.

`listing.json` is copied from the exported `extensions.com.openai.interface`.
Make metadata fixes in the canonical source, export again, and rerun preparation;
editing this draft does not change the upload ZIP.

Complete publisher verification, the portal's domain challenge, OAuth and scans.
Confirm the saved URL retains `toolsets=all&readonly=true`. Complete the
five-positive/three-negative worksheet against a dedicated synthetic reviewer
account and provide a demo URL. Enter reviewer credentials only in the secure
portal, never in this bundle. Resolve required findings, submit for review,
then obtain publication approval before publishing the approved version.
Guide: https://developers.openai.com/plugins/deploy/submission

Pending:
""" + "".join(f"- {item}\n" for item in pending) + f"\nStatus: {label}. No upload or submission has been made.\n"
    prepared = {
        "README.md": readme.encode(), "release.json": encoded(manifest),
        plugin_name: archive, plugin_name + ".sha256": f"{digest(archive)}  {plugin_name}\n".encode(),
        "release-inventory.json": inventory, "CHANGELOG.md": files["CHANGELOG.md"],
        "claude/entry.json": encoded(entry), "claude/catalog.patch": patch.encode(),
        "claude/PR.md": claude_pr.encode(), "cursor/submission.md": cursor.encode(),
        "openai/listing.json": encoded(interface), "openai/review-cases.json": encoded(review_worksheet(files)),
        "openai/submission.md": openai.encode(),
    }
    prepared["SHA256SUMS"] = "".join(f"{digest(content)}  {name}\n"
                                      for name, content in sorted(prepared.items())).encode()
    output.mkdir(parents=True, exist_ok=False)
    for name, content in prepared.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    bundle_path = output / bundle_name
    with zipfile.ZipFile(bundle_path, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in sorted(prepared.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, content)
    (output / (bundle_name + ".sha256")).write_text(f"{digest(bundle_path.read_bytes())}  {bundle_name}\n")
    return manifest, bundle_path


def summary(manifest):
    return (f"## Marketplace preparation: {manifest['stage']}\n\n"
            f"Candidate: `{manifest['candidate_sha']}`; target: `{manifest['tag']}`.\n\n"
            "Download the marketplace-preparation artifact (or the bundle attached to the approved release). "
            "It contains the exact plugin ZIP, checksums, listing drafts and a Claude catalog patch.\n\n"
            + "".join(f"- {'OpenAI' if provider == 'openai' else provider.title()}: {url}\n"
                      for provider, url in PORTALS.items())
            + "\nPreparation only. No provider submission, tag or branch promotion is performed.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    manifest, bundle = prepare(json.loads(args.export.read_text()), args.tag, args.candidate,
                               args.catalog.read_text(), args.catalog_commit, args.output,
                               preview=args.preview)
    if args.summary:
        with args.summary.open("a") as stream:
            stream.write(summary(manifest))
    print(json.dumps({"bundle": str(bundle), "sha256": digest(bundle.read_bytes()), "stage": manifest["stage"]}))
