# 25. Signed-coverage audit tier (houba audit --signed)

Date: 2026-06-16

## Status

Accepted

Builds on [14. Coverage audit](0014-coverage-audit.md) and is unblocked by
[19. Complete attestation coverage](0019-complete-attestation-coverage.md).

## Context

The coverage audit (ADR 0014) classified images by the *annotation stamp* alone and explicitly
deferred the signed-attestation tier until every path was attested. That is now delivered, so the
audit can distinguish *signed* provenance from a stamp that merely proves houba touched the image —
turning the verifiable front door into a trustworthy one.

## Decision

Add an opt-in `--signed` flag to `houba audit`. For each *stamped* image it probes
`RegistryPort.list_referrers(ref, COSIGN_ATTESTATION_ARTIFACT_TYPE)` — the same heuristic
`reconcile` uses for idempotent backfill (a present cosign bundle ⇒ signed; no pull-and-verify).
Signatures are probed **only on covered images** (an uncovered image already fails the base gate).
The report gains a per-image `signed` flag (`None` when not probed) and `signed`/`unsigned` counts;
`--fail-on-unsigned` is an opt-in CI gate (implies `--signed`) mirroring `--fail-on-uncovered`. The
base sweep is unchanged — `--signed` adds one referrer read per stamped image only.

No new port, adapter, actor, or external system was introduced (reuses `list_referrers`).
**C4 model: unchanged.**

## Consequences

- The audit reports three tiers — `uncovered < stamped < signed` — making *trustworthy* coverage
  measurable and CI-gateable.
- Detection trusts the presence of a cosign bundle (no cryptographic verification) — same ceiling
  as reconcile; a heavier verify tier remains a possible follow-up.
- Exit code 1 on an unsigned gate breach is consistent with `--fail-on-uncovered`.

Full design spec: [2026-06-16-signed-coverage-audit-design.md](../../superpowers/specs/2026-06-16-signed-coverage-audit-design.md)
