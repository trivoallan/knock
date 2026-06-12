# 6. SLSA / in-toto attestation

Date: 2026-06-11

## Status

Accepted

Builds on [1. MirrorPolicy format & reconcile contract](0001-mirror-policy-format.md)

## Context

The roadmap's first Phase-C item is "the label is the product" — freeze the provenance
contract. The cheap, scanner-readable layer (OCI-standard annotations + `io.houba.*`
lineage) is already delivered by `domain/stamp.py`. The heavy, cryptographically
verifiable layer is still missing.

## Decision

Add SLSA / in-toto attestations on top of the annotation stamp: two attestations by
design (build provenance + transform/SBOM evidence), configured via `HOUBA_ATTEST_*`,
placed per the hexagonal layering and built on the rebuild path (`buildkit_cli`).

## Consequences

Provenance becomes cryptographically verifiable, not merely readable. Approved design;
implementation still pending (roadmap ①).

Full design spec: [2026-06-11-slsa-attestation-design.md](../../superpowers/specs/2026-06-11-slsa-attestation-design.md)
