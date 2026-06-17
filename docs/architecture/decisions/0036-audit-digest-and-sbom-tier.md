# 36. `houba audit` gains a digest on every outcome + an `--sbom` tier

Date: 2026-06-17

## Status

Accepted

Serves the Backstage coverage-portal design (ADR 0035, separate branch). Builds on the
both-paths SBOM referrer from [34. unify-SBOM-on-syft](0034-unify-sbom-on-syft.md).

## Context

The coverage portal consumes `houba audit`'s JSON report rather than re-walking the registry. It
joins images **by digest** (the tag is mutable; the digest survives Harbor's fan-out) and needs to
know whether a package SBOM is present — both facts the report did not carry.

## Decision

- `CoverageOutcome` gains `digest` (the join key, on every resolvable outcome) — sourced by having
  `RegistryPort.get_annotations` return `(digest, annotations)` from one light `image digest` read,
  not a config-fetching `inspect()`.
- An observational `--sbom` tier (twin of `--signed`): `CoverageOutcome.sbom`, `with_sbom` /
  `without_sbom` counts, probing the SBOM media types from `domain/sbom.py` on covered images only.
- **No `--fail-on-no-sbom` gate** (YAGNI); `audit_exit_code` is unchanged.

## Consequences

- The audit report is the portal's supply-side data source, keyed by digest, with provenance + SBOM
  tiers — no registry credentials in the portal.
- Detection trusts referrer presence (no cryptographic verification) — same ceiling as `--signed`.

Full design: [the spec](../../superpowers/specs/2026-06-17-audit-digest-and-sbom-tier-design.md)
