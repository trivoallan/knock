---
title: "Glossary"
description: "houba's domain vocabulary — the stamp, provenance, SBOM, transform, and lifecycle terms, each linked to its full treatment."
sidebar_position: 5
---

houba's vocabulary is precise: words like *stamp*, *front door*, and *blast-radius* carry specific technical meanings within the tool. This page defines each term as houba uses it.

### alias

A destination tag that tracks a moving target — for example, `{major}.{minor}` always resolves to the highest patch release in that minor, and `latest` always resolves to the highest overall release. houba maintains aliases as the tag selection changes, repointing them after each reconcile. See [redis example](examples/redis.md).

### attach (scan)

`houba attach` ingests an upstream scan report (e.g. SARIF) and stamps it as a signed OCI referrer on the image's digest, recording it as provenance without coupling it to a specific tag. The `--fail-on <severity>` flag turns `attach` into a CI gate: it exits 1 when the report contains any finding at or above the threshold, else 0. See [Attach a scan report](../how-to/attach-scan.md).

### attestation

A signed in-toto statement attached to an image digest as an OCI referrer — carrying a transform, SLSA, scan, or SBOM predicate — signed via cosign under houba's identity. Attestations travel with the digest so the evidence survives retagging. See [Attestations](../explanation/attestations.md).

### audit

`houba audit` walks the registry roster and reports front-door coverage tier by tier — uncovered < stamped < signed < has-SBOM — so operators can measure and enforce the mandate. See [Audit coverage](../how-to/audit-coverage.md).

### blast-radius

The incident-time question: "which images ship the vulnerable package, and who owns them?" houba produces the two artefacts that answer it — the stamp (lineage + owners) and the SBOM (package inventory). The actual query runs in the org's own observability stack; houba never runs it. See [Package-level SBOM](../explanation/sbom.md).

### copy path

Placement of an image whose policy declares no `transform`: the image is copied byte-for-byte via regctl and then stamped with provenance and an SBOM referrer. Contrast with the [rebuild path](#rebuild-path). See [Architecture](../explanation/architecture.md).

### coverage

The share of the fleet that carries the stamp, signature, or SBOM. houba's value is proportional to coverage, because provenance that exists on only some images cannot answer fleet-wide blast-radius queries — "coverage gates value." See [Audit coverage](../how-to/audit-coverage.md).

### deletion mode (mark / purge)

How houba removes a tag that falls out of selection. `purge` hard-deletes immediately; `mark` attaches a pending-deletion referrer for an external, usage-gated reaper to act on later. `mark` is the safe default when production usage is not yet observable. See [Deletion and retention](../explanation/deletion-and-retention.md).

### front door (stamper)

houba's defining role: the single mandatory entry point through which external images enter the org, hardening and stamping them before any workload can pull them. It is a *stamper*, not an image mirror — the stamp is the product. See [Architecture](../explanation/architecture.md).

### gc

`houba gc` garbage-collects superseded scan-result referrers across the registry roster, keeping the N newest per `(tool, format)` pair that are older than a configurable grace window. See [GC scan referrers](../how-to/gc-scan-referrers.md).

### hardening

Rebuilding an image through declarative transforms — injecting an internal CA bundle, rewriting package sources to an internal mirror, setting a timezone — so it meets org policy before placement. Any policy that declares a `transform` triggers the rebuild path instead of the copy path. See [Rebuild and harden](../how-to/rebuild-and-harden.md).

### in-toto

The attestation framework whose statement format houba signs (as DSSE envelopes) to carry transform, scan, and SBOM provenance alongside placed images. houba signs in-toto statements via cosign rather than authoring its own envelope format. See [Attestations](../explanation/attestations.md).

### MirrorPolicy

The declarative YAML artifact that is houba's product policy: an upstream source, a tag selection rule, an optional transform, and one or more destinations. Everything houba does is driven by a MirrorPolicy; nothing happens outside of one. See [MirrorPolicy schema](schemas/mirror-policy.md).

### OCI referrer

An artifact attached to an image digest via the OCI referrers API — SBOM documents, cosign signatures, scan reports, pending-deletion marks. Referrers are keyed to the digest, not the tag, so they survive retagging and alias updates but do not replicate through tools that only handle manifests. See [Package-level SBOM](../explanation/sbom.md).

### provenance

The standardized, portable stamp houba writes on every placed image: OCI-standard annotation keys (`org.opencontainers.image.source`, `.revision`, `.base.name`, `.base.digest`, `.created`) plus `io.houba.*` facts — artifact type, policy/import/variant identity, owners (Backstage entity-ref strings), and transform lineage. No location fact is ever stamped; the same digest can live in many registries. See [Architecture](../explanation/architecture.md).

### rebuild path

Placement of an image whose policy declares a `transform`: the image is rebuilt through BuildKit applying the declared hardening steps, then stamped and given an SBOM referrer. The presence of any transform in the policy is the sole trigger. Contrast with the [copy path](#copy-path). See [Rebuild and harden](../how-to/rebuild-and-harden.md).

### reconcile

`houba reconcile` is the core placement loop: given a MirrorPolicy, it selects the matching tags upstream, copies or rebuilds each one, writes the provenance stamp, attaches an SBOM referrer, retags aliases, and removes tags that have fallen out of selection. See [Getting started](../tutorials/getting-started.md).

### retention (archive)

Capping valid, in-selection tags via the `archive: {keep, olderThanDays}` policy field: houba keeps the N most-recently-imported tags and marks the older surplus pending-deletion. Retention always uses the `mark` deletion mode — it never hard-deletes — so a usage oracle can veto reaping of in-use images. See [Deletion and retention](../explanation/deletion-and-retention.md).

### SBOM

A package-level Software Bill of Materials generated by syft on every placed image (SPDX and/or CycloneDX format) and attached as an OCI referrer. The SBOM is the package inventory that makes blast-radius queries possible. See [Package-level SBOM](../explanation/sbom.md).

### SLSA

Supply-chain Levels for Software Artifacts. On the rebuild path, BuildKit emits a `slsa.dev/provenance/v1` attestation recording the build inputs; houba signs and attaches it as an OCI referrer alongside the image. See [Attestations](../explanation/attestations.md).

### stamp

The act of writing provenance annotations — and attaching SBOM and attestation referrers — onto a placed image. The stamp is what makes an image traceable and its blast-radius queryable. "The label is the product." See [Architecture](../explanation/architecture.md).

### transform

A declarative hardening primitive in a MirrorPolicy (`injectCA`, `rewritePackageSources`, `setTimezone`). Declaring one or more transforms in a policy switches the import from the copy path to the rebuild path; their application is recorded in the provenance stamp. See [Attestations](../explanation/attestations.md).

### usage oracle

An external command configured via `HOUBA_USAGE_ORACLE_CMD` that `houba purge` consults before reaping a marked tag. The oracle answers "was this image's content seen in production recently?" — if yes, houba skips the deletion, protecting live workloads from being pulled from under active deployments. See [Purge unused tags](../how-to/purge-unused-tags.md).
