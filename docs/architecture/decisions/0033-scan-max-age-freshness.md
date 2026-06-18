# 33. Scan freshness — max-age enforced at admission against signed `attested_at`

Date: 2026-06-16

## Status

Accepted.

Builds on [15. Sign the houba attach scan referrer](0015-scan-attestation.md),
[32. `attach` is scan provenance, not a store](0032-attach-is-scan-provenance-not-a-store.md).

## Context

ADR 0032 left an explicit gap: an admission controller verifies a scan was *signed*, but a valid
signature over a *stale* scan still passes. The named remedy — and the only one inside the 0032
boundary — is a provenance-shaped **max-age** ("scanned recently"), never vulnerability correlation
(currency stays Dependency-Track's job).

## Decision

- **Locus = producer-side.** houba *produces* the freshness fact; the admission controller
  *enforces* max-age against it. houba gains no audit-side freshness tier — an audit tier reports
  drift but cannot block a deploy, so it does not close the gap.
- **Clock = the existing signed `ScanPredicate.attested_at`.** No new predicate field; the frozen
  `/scan/v1` schema is unchanged. Semantics: *"houba (re)attached a scan at T."* Rejected: a scanner
  report-time field (format-dependent, often absent, and a frozen-API mutation for marginal gain).
- **Make the contract explicit and published.** A field description on `attested_at`, and the
  predicate schema is now rendered to `docs/reference/schemas/scan-predicate.md` (it was derivable but never
  published), bringing it under the CI drift gate.
- **Precondition:** enforcement requires `HOUBA_ATTEST_SIGNER`; admission reads the *signed*
  `attested_at`, never the unsigned `io.houba.scan.timestamp` annotation (which stays, for `gc`).

## Consequences

- No code change beyond a field description + the reference generator; no new domain logic, no schema
  field, no new CLI verb.
- **Re-attaching an old report resets the clock** — accepted, mitigated by CI scan-then-attach
  discipline; not houba's to police (non-goal).
- **No C4 change** (consistent with ADR 0032: admission stays the abstract consumer).
- A Kyverno worked example demonstrates the gate (`docs/examples/admission/`).

Full design spec:
[2026-06-16-scan-max-age-design.md](../../superpowers/specs/2026-06-16-scan-max-age-design.md)
