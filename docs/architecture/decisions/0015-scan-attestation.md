# 15. Sign the knock attach scan referrer

Date: 2026-06-13

## Status

Accepted

Builds on [6. SLSA / in-toto attestation](0006-slsa-attestation.md)

## Context

`knock attach` attaches an upstream scan report as an unsigned OCI referrer. #49 added a generic
`AttestorPort` (cosign) for the rebuild path. Verifiable scan provenance lets a downstream
admission controller require a signed scan.

## Decision

When a signer is configured (`KNOCK_ATTEST_SIGNER`), `knock attach` also emits a signed in-toto
attestation with predicate type `https://knock.dev/predicate/scan/v1` over the image digest. It is
**additive** (the raw report referrer is always attached) and **off by default**. A signing failure
fails the attach (exit 2) — no silent gap. knock is the attester; the predicate records the upstream
scanner, not a claim that knock scanned. The `AttestorPort` is reused unchanged; only a pure-domain
statement builder and use-case/CLI wiring are added.

## Consequences

Scan results become cryptographically verifiable, unlocking admission enforcement. One more predicate
type frozen as public API (`/scan/v1`), schema derived from Pydantic. No new external system: reuses
the Signing service and Transparency log systems introduced by #49 — the knock→signer C4 edge now
also covers `knock attach` (signing the scan referrer).

Full design spec: [2026-06-13-scan-attestation-design.md](../../superpowers/specs/2026-06-13-scan-attestation-design.md)
