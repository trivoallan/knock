# Signed-coverage audit tier

Date: 2026-06-16
Status: Design (approved)
Roadmap: *Now* — "Signed-coverage audit tier". Follow-up to ④ (coverage audit, ADR 0014),
unblocked by complete attestation coverage (ADR 0019).

## Problem

`houba audit` today classifies each registry image as `covered` / `uncovered` from the
*annotation stamp* alone (`domain/coverage.py:is_stamped` → `{prefix}.policy`, read via the
lightweight `RegistryPort.get_annotations`). A stamp is cheap to forge or copy; it proves houba
*touched* the image, not that the provenance is *trustworthy*. Now that every path (copy, rebuild,
backfill) carries a **signed** attestation, the audit can distinguish *signed* from *merely
stamped* — turning the verifiable front door into a trustworthy one without misleading.

## Design

A third tier on the existing ladder: `uncovered < stamped < signed`. Opt-in, so the base sweep
stays as cheap as today (one read per image).

### Detection (reuse, no new abstraction)

An image is **signed** iff it carries a cosign attestation referrer — exactly the heuristic
`reconcile` already uses for idempotent backfill: `list_referrers(ref,
COSIGN_ATTESTATION_ARTIFACT_TYPE)` non-empty ⇒ signed. No pull+verify (same documented ceiling as
reconcile: a present cosign bundle ⇒ "houba signed this digest"). The test is `bool(referrers)` —
no dedicated domain predicate is added.

### Use case (`use_cases/audit.py`)

- `audit_coverage(..., check_signed: bool = False)`.
- `CoverageOutcome.signed: bool | None = None` — `None` when not probed; `True`/`False` when
  probed. Set **only** for covered images when `check_signed` is on.
- Signatures are probed **only on stamped (covered) images.** An uncovered image already fails the
  base gate; its signature status is irrelevant and probing it would waste a read.
- `CoverageCounts` gains `signed: int` and `unsigned: int`, counted only among covered+probed
  images (`signed + unsigned == covered` when `check_signed`).
- `audit_exit_code(..., fail_on_unsigned: bool = False)`: after the existing logic (per-image read
  errors dominate; then `fail_on_uncovered`), exit 1 when `fail_on_unsigned and unsigned > 0`.

### CLI (`cli/audit.py`)

- `--signed` → `check_signed=True`.
- `--fail-on-unsigned` → passed to `audit_exit_code`; **implies `--signed`** (if given alone, the
  command turns the probe on rather than erroring), mirroring the safe-default opt-in pattern of
  `--fail-on-uncovered`.
- Text render: a new `UNSIGNED <ref>` line for covered-but-unsigned images (only in `--signed`
  mode); summary line gains `signed=N unsigned=N`. JSON is structurally unchanged — the new fields
  simply appear.

### Cost

`--signed` adds one `list_referrers` read per **stamped** image only. The default sweep is
unchanged. Sequential, like the rest of audit/purge (concurrency stays deferred).

## Out of scope

- Cryptographic verification of the signature (pull + verify the DSSE bundle) — same ceiling as
  reconcile; a separate, heavier tier if ever needed.
- Probing signatures on uncovered images.

## Testing

- Unit (`use_cases/audit.py`): fake registry seeded with/without attestation referrers →
  `signed`/`unsigned` counts and per-outcome `signed` flag; `signed` stays `None` when
  `check_signed` is off and on uncovered images.
- Unit (`audit_exit_code`): `fail_on_unsigned` gate; read-error code still dominates.
- CLI: `--signed`, `--fail-on-unsigned` implies probe, `UNSIGNED` line + summary fields.
- `CoverageReport` JSON Schema regenerated (derived, already published).

## Docs / C4

No new actor, external system, port, or adapter (reuses `RegistryPort.list_referrers`). **C4
model: unchanged.** Update the `houba audit` walkthrough in `docs/examples/README.md` (replace the
"signed-attestation coverage is a later tier" note with the delivered `--signed` flow) and add a
thin ADR (0025) linking here.
