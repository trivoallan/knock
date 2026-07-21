# 34. Unify SBOM generation on syft (both paths)

Date: 2026-06-17

## Status

Accepted. Supersedes (in part) [ADR 0029](0029-sbom-generation.md) — the SBOM *mechanism*
only; 0029's value proposition (package-level blast-radius) and depth findings stand.

## Context

ADR 0029 generated an SPDX SBOM on the rebuild path only, via buildkit's native scanner,
attached as an image-index attestation manifest. Two forces make that shape wrong: (1) a
real CycloneDX need — buildkit's `attest:sbom` emits only SPDX, so any consumer needing
CycloneDX forces a standalone generator regardless; (2) buildkit's attachment is an
index-attestation manifest while a copy-path SBOM can only be an OCI referrer — two storage
locations, fracturing the "one query answers blast-radius" promise and the future audit
probe.

## Decision

One tool, one mechanism, configurable formats. A standalone `SbomGeneratorPort` (driven by
syft) scans the **placed image by digest** on **both** paths and returns one document per
configured format; each is attached as an **OCI referrer**. buildkit's `attest:sbom` (and
`BuildRequest.sbom`) is dropped; `attest:provenance` stays. Format set is global config
`KNOCK_SBOM_FORMATS` (default `["spdx-json"]`, non-empty ⇒ always-on). syft is the same
engine buildkit packaged, so 0029's depth findings carry over.

## Consequences

- A new port + adapter (syft, a bundled CLI driven by subprocess) — the C4 Component view
  changes (0029 said "C4 unchanged"; no longer true). The buildkit adapter loses its
  SBOM responsibility.
- The rebuild path (~99% of intake) now does a post-push scan instead of a free in-build
  attestation — accepted cost for one tool / one mechanism / CycloneDX-anywhere.
- The audit "has SBOM" dimension (follow-up) simplifies to a single referrer probe.
- Transition: images already rebuilt under 0029 carry an index-attestation SBOM, not a
  referrer one; the future audit dimension (and optional backfill) reconciles them.

Full design spec:
[2026-06-17-sbom-copy-path-unify-syft-design.md](../../superpowers/specs/2026-06-17-sbom-copy-path-unify-syft-design.md)
