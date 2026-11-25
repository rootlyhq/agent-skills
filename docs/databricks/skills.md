# Publish canonical skills to Unity Catalog

Databricks documents two distribution destinations:

| Destination | Publishes | Access model |
|---|---|---|
| Public Databricks Marketplace | Hosted MCP connection | Provider listing and consumer installation |
| Unity Gateway Skills | `SKILL.md` folders in Unity Catalog | Explicit grants in the destination metastore |

The official [skills overview](https://docs.databricks.com/aws/en/agents/uc-skills)
describes organizational discovery and sharing, currently in Beta. This is not
evidence of a public Marketplace listing for standalone skills. Confirm any
cross-customer distribution offer with Databricks before promising one.

## Prepare a destination

Have an authorized administrator enable the skills preview and select a standard
Unity Catalog schema with managed storage. Publishers need parent catalog/schema
access and permission to create skills; updates require read/write access to
existing skill bundles. Consumers need parent access and `READ VOLUME`.
Ownership or `MANAGE` controls sharing. Skills are reachable from workspaces
assigned to their metastore; a Rootly-owned schema does not automatically make
them available to every Databricks customer.

Use [Govern skills](https://docs.databricks.com/aws/en/ai-gateway/govern-skills)
for exact grants and feature restrictions. Publishing a skill does not grant
Rootly account access or install the operational MCP service.

## Keep this repository canonical

Publish the existing folders under `skills/`, including their supporting files.
Do not maintain a second set of instructions for Databricks. A reviewed mapping
can explicitly select the seven incident workflows:

```yaml
version: 1
skills:
  - path: skills/alert-triage
    target: demo.rootly_skills.alert-triage
  - path: skills/deploy-check
    target: demo.rootly_skills.deploy-check
  - path: skills/incident-communications
    target: demo.rootly_skills.incident-communications
  - path: skills/incident-response
    target: demo.rootly_skills.incident-response
  - path: skills/on-call
    target: demo.rootly_skills.on-call
  - path: skills/retrospective
    target: demo.rootly_skills.retrospective
  - path: skills/service-health
    target: demo.rootly_skills.service-health
```

`demo.rootly_skills` is a placeholder, not a configured destination. Review new
workflows and their permissions before adding them to a publishing mapping.

## Choose a publishing mechanism

The [create/share tutorial](https://docs.databricks.com/aws/en/agents/uc-skills/create-share-uc-skills)
supports interactive publication and GitHub-managed publication. For interactive
work, the Databricks Skills MCP server returns CLI instructions; it does not run
uploads itself. Review the commands and destination before authorizing writes.

For this Git-managed repository, the official
[publishing action](https://github.com/databricks/unity-gateway/tree/main/actions/publish-skills)
can use the mapping directly. It runs on a GitHub runner and does not require a
Databricks notebook or compute job. Use an approved publishing service principal,
reviewed action SHA and protected deployment environment. GitHub OIDC can avoid
a stored Databricks client secret; see the
[administrator setup](https://github.com/databricks/unity-gateway/blob/main/actions/publish-skills/docs/authentication.md).

The upstream quickstart publishes on matching pushes. Any workflow added here
must preserve this repository's explicit publication approval, using reviewed
inputs and a manual/protected publishing step. No publishing workflow or remote
identity is configured by this documentation change.

A dry run validates local folders without testing Databricks authentication or
grants. Inspect actual publication results and source/bundle hashes afterward.
Updates can partially succeed; stale remote files, renames and deletions require
deliberate review. Publication does not automatically share skills with consumers.

## Share and consume

An authorized owner grants access to the published skills. Consumers can download
a snapshot or connect to the schema for live loading. The
[consumer tutorial](https://docs.databricks.com/aws/en/agents/uc-skills/use-uc-skills)
documents the supported Unity Gateway CLI setup. After authentication, a live
schema connection uses a command of this form:

```sh
ug skills add --location demo.rootly_skills --via mcp
```

The Databricks Skills MCP connection provides instructions. The Rootly MCP
connection provides operational tools. Configure and validate both, including
the [read-only boundaries](security.md), before an incident workflow uses live data.
