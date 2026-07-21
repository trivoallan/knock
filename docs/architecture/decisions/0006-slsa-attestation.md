# 6. SLSA / in-toto attestation

Date: 2026-06-11

## Status

Accepted

Builds on [1. MirrorPolicy format & reconcile contract](0001-mirror-policy-format.md)

## Context

The roadmap's first Phase-C item is "the label is the product" — freeze the provenance
contract. The cheap, scanner-readable layer (OCI-standard annotations + `io.knock.*`
lineage) is already delivered by `domain/stamp.py`. The heavy, cryptographically
verifiable layer is still missing.

## Decision

Add SLSA / in-toto attestations on top of the annotation stamp: two attestations by
design (build provenance + transform/SBOM evidence), configured via `KNOCK_ATTEST_*`,
placed per the hexagonal layering and built on the rebuild path (`buildkit_cli`).

## Consequences

Provenance becomes cryptographically verifiable, not merely readable. **Implemented**
(roadmap ①, plan `docs/superpowers/plans/2026-06-13-slsa-attestation.md`): a pure-domain
transform predicate (`knock/domain/attestation.py`, `predicateType:
https://knock.dev/predicate/transform/v1`), a pluggable `AttestorPort` with a single
`cosign` adapter (keyless / kms / key), and BuildKit's native `slsa.dev/provenance/v1`.
Off by default (`KNOCK_ATTEST_SIGNER=""`), rebuild-only in v1.

**Deviation from the design spec, ratified:** the spec §4 sketched `tenacity` retry in the
cosign adapter. To honor the load-bearing CLAUDE.md invariant ("no retry logic anywhere"),
the adapter is instead a thin fail-fast subprocess wrapper like `regctl`/`buildctl` —
`cosign` already retries transient network calls internally. No `tenacity` dependency added.

Full design spec: [2026-06-11-slsa-attestation-design.md](../../superpowers/specs/2026-06-11-slsa-attestation-design.md)
