# 14. Sign the houba attach scan referrer

Date: 2026-06-13

## Status

Accepted

Builds on [6. SLSA / in-toto attestation](0006-slsa-attestation.md)

## Context

`houba attach` attaches an upstream scan report as an unsigned OCI referrer. #49 added a generic
`AttestorPort` (cosign) for the rebuild path. Verifiable scan provenance lets a downstream
admission controller require a signed scan.

## Decision

When a signer is configured (`HOUBA_ATTEST_SIGNER`), `houba attach` also emits a signed in-toto
attestation with predicate type `https://houba.dev/predicate/scan/v1` over the image digest. It is
**additive** (the raw report referrer is always attached) and **off by default**. A signing failure
fails the attach (exit 2) — no silent gap. houba is the attester; the predicate records the upstream
scanner, not a claim that houba scanned. The `AttestorPort` is reused unchanged; only a pure-domain
statement builder and use-case/CLI wiring are added.

## Consequences

Scan results become cryptographically verifiable, unlocking admission enforcement. One more predicate
type frozen as public API (`/scan/v1`), schema derived from Pydantic. No new external system: reuses
the Signing service and Transparency log systems introduced by #49 — the houba→signer C4 edge now
also covers `houba attach` (signing the scan referrer).

Full design spec: [2026-06-13-scan-attestation-design.md](../../superpowers/specs/2026-06-13-scan-attestation-design.md)
