# Microsoft 365 Copilot Cowork

Rootly for Copilot packages the canonical skills for Microsoft Copilot Cowork.
It is a separate app from Rootly's existing Microsoft Teams app. Keep their app
identities and Partner Center offers separate when updating either product.

## Package format

The Microsoft upload is a Microsoft 365 app ZIP, not the generic plugin ZIP
produced by this repository's release exporter. Its root contains:

```text
manifest.json
color.png
outline.png
skills/<skill-name>/SKILL.md
skills/<skill-name>/references/...
```

Keep `skills/` canonical. Copy the selected source commit's skill files unchanged
into the package; do not maintain a second set of Microsoft-specific instructions.
The adapter explicitly selects the seven incident workflows. Adding another
canonical skill does not automatically include it in the Microsoft package.
An update must explicitly review any new skill and its connection requirements.

`tools/scripts/build_package.py` generates `adapters/microsoft/manifest.json`
from `VERSION` and thin metadata in `tools/scripts/microsoft_manifest.py`.
The packaging script takes its inputs from the verified generic export and
compares them against the exact candidate commit. It performs no network calls.

The manifest declares each skill folder in `agentSkills` and Rootly's remote MCP
connection in `agentConnectors`. Use Rootly's real icons, developer identity,
privacy URL and terms URL; replace any generated placeholders. Preserve the
existing Microsoft app ID for updates. Reviewed PNG icons live in
`assets/microsoft/`; their exact bytes are pinned for publication scanning.

## Build and download

After committing the reviewed source, prepare a local test package:

```sh
mkdir -p dist
python3 tools/scripts/export_release.py > dist/export.json
python3 tools/scripts/build_microsoft_package.py --export dist/export.json \
  --tag "v$(cat VERSION)" --candidate "$(git rev-parse HEAD)" \
  --output dist/microsoft-preview --preview
```

Use a fresh output directory. Dirty or mismatched exported source is rejected by the
candidate comparison.

Validation runs upload a **microsoft-package-preview** Actions artifact with a
ZIP, checksum, source/file inventory and instructions. Download the artifact,
extract it, and use the inner `rootly-microsoft-preview-<SHA>.zip` for a private
test installation. Preview instructions do not establish host or provider
validation, and previews must not be submitted publicly.

The approved Release workflow attaches `rootly-microsoft-v<VERSION>.zip`, its
`.sha256` and a corresponding `-inventory.json` to the GitHub Release. Download
that ZIP directly for an authorized provider submission. It has no outer folder.
The generic plugin ZIP and marketplace-preparation bundle are different files.

For final preparation, replace `--preview` with
`--expected-sha256 <reviewed-microsoft-zip-sha256>` and use a fresh destination.
Final preparation requires dated release metadata. A mismatched checksum fails
before any output is written. See [release approval](https://github.com/rootlyhq/agent-skills/blob/main/docs/releasing.md#explicit-publication)
for the protected workflow and its separate checksums.

The initially validated package uses `manifestVersion: "devPreview"`, generated
by Agents Toolkit. Microsoft documents different schema requirements across
versions. Check the current [package development guide](https://learn.microsoft.com/en-us/copilot/cowork/cowork-plugin-development)
and validate the actual ZIP before changing its schema. A Developer Portal
validation pass does not imply marketplace certification or publication.

## Authentication and permissions

The Microsoft package uses this connection:

```text
https://mcp.rootly.com/mcp?toolsets=all
```

It intentionally omits the connector's `authorization` object to use automatic
[OAuth Dynamic Client Registration](https://learn.microsoft.com/en-us/copilot/cowork/cowork-plugin-development#dynamic-client-registration).
Do not retain an importer's placeholder `OAuthPluginVault` registration or add
manually managed client credentials for this flow. Installation and OAuth consent
are separate steps. Verify the connected workspace after signing in.

This Microsoft-specific URL has no `readonly=true` filter. It does not provide
the server-side write restriction described for the default repository connection
in [installation](install.md#read-only-restrictions). The incident workflows still
only recommend and draft. Request the identity permissions required to sign in
and the incident-response/on-call read permissions needed by the workflows;
leave unnecessary write, AI, log and notification-contact permissions unselected.
Check each consent tab separately. A skill instruction is not a security boundary.
Keep the default repository URL and generated read allowlists unchanged.

## Validate an update

1. Pin the exact reviewed source commit and version. Build in a clean directory,
   compare the packaged skill files with that commit, and record the ZIP checksum.
2. Validate the ZIP in the Microsoft Developer Portal and check the stored
   manifest, including its app ID, skill list and MCP URL. Use a separate test
   installation before changing the marketplace package.
3. In a tenant with Cowork access, check the assigned Copilot license, usage
   billing and applicable admin policy. These are tenant prerequisites, not files
   supplied by the plugin. Check current Microsoft requirements before provisioning.
4. Install privately, authenticate through DCR and verify the intended Rootly
   workspace. Read a small permitted incident/service/on-call sample. Do not
   exercise write tools against live Rootly data.
5. Load each packaged skill with clearly labeled fictional evidence. Check
   evidence grounding, missing information and draft-only behavior. This host
   acceptance check does not replace the [evidence-fidelity release gate](https://github.com/rootlyhq/agent-skills/blob/main/tools/tests/README.md).
6. Validate the dedicated certification account separately: password/sign-in
   method, workspace, incident access and on-call access. Distinguish an empty
   schedule list from a permission error. Do not infer reviewer access from a
   maintainer's successful connection.

## Submit and retain evidence

Use [Partner Center Marketplace offers](https://partner.microsoft.com/dashboard/v2/marketplace-offers/overview)
and the existing **Rootly for Copilot** offer. Complete product setup, packages,
properties, marketplace listings, availability and certification information.
The public offer targets organizations beyond the development tenant.

Upload branded screenshots with alt text. Use actual host UI and label fictional
demo data. The initial assets are three 1366 by 768 PNGs; retain their editable
sources and provenance with the private submission records.

Certification instructions should identify Cowork as the host, describe DCR,
provide bounded test prompts and expected results, and disclose service/license
requirements. Enter the dedicated reviewer credentials only in Microsoft's
certification fields, retrieving them from the approved password manager. Never
commit credentials or include them in screenshots, logs or handoff documents.

Before submitting, obtain the required authorization for that publication.
After submitting, verify the offer's actual status and retain a credential-free
receipt. **Pre-processing**, **Certification** and **Publish** are distinct
stages; an accepted submission is not a live listing. Check for certification
feedback before replacing or resubmitting the package.

The release workflow prepares and attaches the Microsoft package; it does not
submit to Partner Center, authorize OAuth, change tenant settings or claim a
listing is live. Its publish job downloads the prepared artifact and verifies
the separately approved Microsoft checksum instead of rebuilding after approval.
Offline checks cover packaging contracts and provenance, not Microsoft's complete
schema validation or live OAuth behavior.

Keep private screenshot sources, reviewer details and validation receipts outside
the public tree. Local continuation notes may live in ignored
`tools/tests/results/<submission>/HANDOFF.md`; they are not available in a fresh
clone. Keep current provider status there rather than claiming publication in
the public README before it is verified.
