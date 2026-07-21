# 21. `attach --fail-on <severity>` CI gate

Date: 2026-06-15

## Status

Accepted

Builds on [15. Sign the knock attach scan referrer](0015-scan-attestation.md) and mirrors the
`--fail-on-uncovered` pattern from [14. Coverage audit](0014-coverage-audit.md).

## Context

`knock attach` is observational by default: it ingests a scan report and stamps it as a portable
OCI referrer, then exits 0. Nothing in the current CLI lets CI enforce a quality gate on the scan
result without a separate tool reading the referrer back.

The roadmap's "Now" band calls for the first enforcement lever: a severity-based CI gate on
`attach` itself, directly at ingest time, so CI can fail a build when a high/critical finding is
present without requiring a second pass.

## Decision

`knock attach` accepts an optional `--fail-on <severity>` flag. Severity order (highest to
lowest): `critical > high > medium > low > unknown`. `unknown` is the lowest targetable bucket
and is folded in only at `--fail-on low` or `--fail-on unknown`; it is excluded at
`--fail-on medium` and above.

Behaviour:
- **Observational by default** — no `--fail-on` flag → always exits 0 after attaching (unchanged
  from before).
- **Gate mode** — with `--fail-on <severity>`, after a successful attach, if the ingested scan
  has any finding at or above the threshold, `attach` writes one line to stderr:
  `gating: scan has a finding at or above <severity> (--fail-on)` and exits 1.
- A scan with no findings at or above the threshold exits 0 (gate passes).
- Adapter/config errors still exit 2/3 regardless (the gate does not suppress I/O errors).

Implementation reuses the existing layers: the pure `gate_breached` (`domain/scan/summary.py`)
decides a breach from the already-parsed severity counts, and `attach_exit_code`
(`use_cases/attach.py`, mirroring `audit_exit_code`) maps it to the process exit code; the CLI
is a thin wrapper. No new port, adapter, actor, or external system was introduced.
**C4 model: unchanged.**

The pattern mirrors `audit --fail-on-uncovered` (ADR 0014): the gate is an opt-in flag, the
default stays safe (non-failing), and the decision logic is a pure domain function with no
side-effects.

## Consequences

- CI pipelines gain a one-liner severity gate at scan-ingest time, with no additional tooling.
- The severity order (`critical > high > medium > low > unknown`) is frozen as public CLI
  contract; changing it would be a breaking change.
- `unknown` findings are excluded from `--fail-on medium`/`high`/`critical` gates, which keeps
  the common CI patterns noise-free while remaining reachable at `--fail-on low`/`unknown`.
- Exit code 1 on a gate breach is consistent with `audit --fail-on-uncovered`.

Full design spec: [2026-06-15-attach-fail-on-design.md](../../superpowers/specs/2026-06-15-attach-fail-on-design.md)
