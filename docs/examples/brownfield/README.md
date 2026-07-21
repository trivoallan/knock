# Brownfield demo — Act 1 corpus

This example places two MongoDB 8.0 images (tags `8.0.15` and `8.0.16`, both affected by
CVE-2025-14847 "mongobleed") through knock's **copy path**: the images are copied from
`docker.io/library/mongo` into the demo registry, stamped with provenance
(`io.knock.owners=group:default/data-platform`, knock's own annotation namespace), and each receives a syft-generated CycloneDX
SBOM attached as an OCI referrer. knock's digest-bound placement with the authoritative
`io.knock.owners=group:default/data-platform` label is exact — in contrast to the tag-only
"before" world (a raw, un-knock'd mirror under a project-named repo, where the owner is only
*guessable* from the first path segment), which is illustrated in the how-to
(`docs/how-to/brownfield-drop-in.md`), not seeded. This sets up the demo's central
question: *which workloads are running the affected package, and who owns them?* — a query the
SBOM inventory plus the stamped label answer and the scanner alone cannot.
