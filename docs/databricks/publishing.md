# Publish the Databricks integrations

Procedures reviewed against official sources on November 12, 2026. Recheck
the current portal and requirements before external actions.

Public MCP listings and governed skill publication use different destinations.
For `SKILL.md` folders, see [Unity Gateway Skills publication](skills.md), including
the official GitHub Action. The documented skills route is organizational Unity
Catalog sharing; a public Marketplace skills submission type has not been
established by the sources reviewed here.

## Marketplace MCP listing

Public Marketplace publication requires provider approval. Follow the
[provider onboarding guide](https://docs.databricks.com/aws/en/marketplace/become-provider)
and the [partner application](https://partners.databricks.com/s/partner-application).
An organization already in the partner program should use the existing-partner
route rather than create a duplicate application. Confirm the required workspace
plan, Unity Catalog setup and Marketplace administrator role.

Prepare a provider identity, brand assets, public support and legal URLs, and a
listing that accurately describes the hosted Rootly service. Create the listing
under **Marketplace → Provider console → Listings** and select the MCP asset.
Use the AI category and DCR authentication. Supply Rootly's HTTPS host, port 443
and `/mcp` path; DCR discovers its OAuth endpoints. A tag on this listing does not
pin a continuously deployed server to this skills repository's release.

Use [Databricks' listing field reference](https://docs.databricks.com/aws/en/marketplace/create-listing#mcp-server-listing-fields)
for the current form. This route publishes a connection to a hosted service;
it does not consume the Claude, OpenAI or Microsoft plugin ZIP. Do not imply
that it installs the canonical Rootly skills or shares a customer incident dataset.

Before publication, validate a private consumer installation, per-user sign-in,
selected tools and a bounded successful read. Check the selected connection's
read-only boundary and any query-parameter propagation. Verify public URLs and
service/pricing disclosures. Retain a credential-free receipt and obtain explicit
publication authorization. Report draft, published and consumer-install states
separately. See [listing maintenance](https://docs.databricks.com/aws/en/marketplace/manage-listings)
for updates and unpublishing; removing a listing is not a universal revocation
of existing data copies or credentials.

## Maintain the integration

Record the deployed server endpoint and the skills source revision separately.
Changing a release tag in this repository does not upgrade or roll back the
hosted server. Recheck discovery, consent, selected tools and bounded reads after
a relevant server, client or configuration change.

The repository's release workflow does not register a Databricks provider,
submit a listing or grant workspace access. Keep current provider state and
private validation receipts outside the public tree. Draft partner messages,
customer permissions, quotes and launch plans also belong outside this repository.
