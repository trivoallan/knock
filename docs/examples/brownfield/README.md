# Brownfield demo — Act 1 corpus

This example places two MongoDB 8.0 images (tags `8.0.15` and `8.0.16`, both affected by
CVE-2025-14847 "mongobleed") through houba's **copy path**: the images are copied from
`docker.io/library/mongo` into the demo registry, stamped with provenance
(`io.houba.owners=group:default/data-platform`, houba's own annotation namespace), and each receives a syft-generated CycloneDX
SBOM attached as an OCI referrer. The `8.0` moving alias is re-pointed by `make seed-incident`
(first to `8.0.15`, then to `8.0.16`) so that the "before" world — a raw, un-houba'd copy under
`team-data-platform/mongo`, where the owner is only *guessable* from the first path segment — is
ambiguous by tag while houba's digest-bound placement with the authoritative
`io.houba.owners=group:default/data-platform` label is exact. This sets up the demo's central
question: *which workloads are running the affected package, and who owns them?* — a query the
SBOM inventory plus the stamped label answer and the scanner alone cannot.
