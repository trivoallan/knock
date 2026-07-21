# 41. `knock verify` — read-side gate over knock's referrers

Date: 2026-06-24

## Status

Accepted.

Builds on [15. Sign the knock attach scan referrer](0015-scan-attestation.md),
[21. `attach --fail-on` severity CI gate](0021-attach-fail-on-gate.md),
[32. `attach` is scan provenance, not a store](0032-attach-is-scan-provenance-not-a-store.md),
[33. Scan freshness — max-age enforced at admission against signed `attested_at`](0033-scan-max-age-freshness.md).

## Context

`attach` writes signed provenance facts (scan attestation, SBOM, stamp) as OCI referrers on a
digest. There is no read-side counterpart: `attach --fail-on` gates at *ingestion* (the wrong
moment for a promotion); `audit` is fleet-wide coverage, not per-digest.

The Kargo scan-gate experiment (validated, 2026-06-23) proved a promotion gate can read knock's
signed scan predicate with zero knock code — but correctly implementing that gate required four
non-obvious pieces: `--insecure-ignore-tlog` in key mode, accumulating all attestations and
picking the freshest by `attested_at`, replicating the `gate_breached` at-or-above-threshold
loop, and ISO-8601 age math (which varies between GNU date and macOS/BusyBox). Every enforcer
that re-implements those pieces is exactly the duplication `attach` exists to prevent.

## Decision

Introduce `knock verify <ref>` — a read-only verb that turns knock's referrer/annotation
conventions into a single exit-0/1 verdict plus a human/JSON report.

**Surface:** `knock verify <ref> [--require scan-pass[,stamp,sbom]] [--max-severity high]
[--max-age 7d] [--registry NAME] [--output text|json]`

**Trust model — cryptographic where it counts:**

- `scan-pass`: reads the **signed** in-toto scan attestation (predicate type
  `https://knock.dev/predicate/scan/v1`) via `cosign verify-attestation`. Severity and
  freshness are evaluated against the signed `summary` / `attested_at`, never the unsigned
  `io.knock.scan.timestamp` annotation. Fail-closed: missing, unverifiable, stale, or
  unparseable attestation all produce exit 1, not exit 2.
- `stamp`: presence of `{KNOCK_LABEL_PREFIX}.artifact.type` on the manifest annotations
  (descriptive coverage fact; the image's own cosign signature is Kyverno's job).
- `sbom`: presence of at least one SPDX (`application/spdx+json`) or CycloneDX
  (`application/vnd.cyclonedx+json`) referrer.

**Architecture:** `verify` is added to `AttestorPort` (sign and verify are the two halves of
one cosign trust tool; no new port or adapter). `CosignAdapter.verify` separates *"cosign ran,
no verifiable attestation"* (→ empty list → domain fail-closes → exit 1) from *"cosign could
not run"* (→ `CosignError` → exit 2). `knock/domain/verify.py` is a pure function over
already-resolved facts, fully unit-testable without fakes.

**Exit-code contract:** 0 = all pass; 1 = gate verdict (breach or fail-closed); 2 = operational
failure; 3 = config error. Gate-1 is always a clean verdict, never an unexpected crash.

## Consequences

- Promotion gates (Kargo `AnalysisTemplate`, a Kyverno sidecar, a CI step) delegate the
  `gate_breached` + freshness + cosign trust logic to `knock verify` instead of re-implementing
  it in shell.
- The fact-split from ADR 0032 is preserved: `--require scan-pass` alone is the Kargo gate;
  `audit` stays fleet-wide; Kyverno keeps admission. `verify` is the general primitive; callers
  opt in to which facts matter.
- `--require scan-pass` requires `KNOCK_ATTEST_SIGNER` (no signer configured → `ConfigError` →
  exit 3). `--require stamp` requires a non-empty `KNOCK_LABEL_PREFIX`.
- `CosignAdapter` gains a `verify` method alongside `attest`; `AttestorPort` is updated to match.
  No new port, adapter, external system, or C4 actor.

Full design spec:
[2026-06-24-knock-verify-design.md](../../superpowers/specs/2026-06-24-knock-verify-design.md)
