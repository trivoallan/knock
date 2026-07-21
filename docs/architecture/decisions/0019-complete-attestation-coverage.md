# 19. Complete attestation coverage — sign the copy path and backfill unsigned mirrors

Date: 2026-06-15

## Status

Accepted

Builds on [6. SLSA / in-toto attestation](0006-slsa-attestation.md) and
[14. Coverage audit](0014-coverage-audit.md).

## Context

knock's value lands at incident time via signed provenance: *the label is the product*, and
*coverage gates value*. The single-front-door mandate has been confirmed by the platform/security
team. Today only the **rebuild** path signs an in-toto attestation — images that knock **copies**
(no transform) or **skips** (already mirrored, digest-stable) carry the OCI / `io.knock.*`
annotation stamp but no signed attestation. The coverage audit (`knock audit`) surfaces this gap;
while two of three paths are unsigned, a signed-coverage query cannot be relied upon for
enforcement.

## Decision

**Every image knock fronts must carry a signed knock attestation**, computed idempotently so each
digest is signed once, not re-signed on every reconcile.

1. **Domain (`domain/reconcile.py`).** `MirrorArtifact` gains `attested: bool` (default `True` —
   safe default, real adapter always sets it explicitly). `VariantReconcile` gains `to_sign:
   list[str]`. `_classify` returns `"sign"` when its decision would be "skip" **and** `not
   attested`; `reconcile_variant` routes those tags into `to_sign`.

2. **Predicate discriminator (`domain/attestation.py`).** `build_transform_statement` gains a
   `transformed: bool` parameter — `True` for the rebuild path, `False` for copy and
   sign-only backfill. Same `predicate_type`, same `/v1` frozen schema; honest about
   hardened-vs-passed-through without a new predicate type.

3. **Use case wiring (`use_cases/reconcile.py`).**
   - *State gathering:* for each already-mirrored tag, call
     `registry.list_referrers(dst_ref, COSIGN_ATTESTATION_ARTIFACT_TYPE)` and set
     `attested = len(refs) > 0`. Port already exists — no new port or adapter.
   - *Copy path:* drop the `and w.vplan.transform` guard from the signing block; sign with
     `transformed=False`.
   - *Sign-only pass (`to_sign`):* for each backfill tag, resolve the current destination digest
     from the state already gathered and call `attestor.attest(dst@digest, statement)` with
     `transformed=False`. No copy, no re-stamp — the annotation stamp is already present.
   - Backfill is reported as a new `"attested"` operation kind, with a matching `Counts.attested`
     total in `ports/reporter.py`.

**C4 model: unchanged.** No new port, adapter, actor, or external system — this reuses the
existing `RegistryPort.list_referrers` and `AttestorPort.attest`.

## Consequences

- Every image knock fronts carries a signed attestation after the first reconcile post-upgrade.
  In steady state the cost is one extra `list_referrers` read per already-mirrored tag; once a
  digest is signed it is never re-signed (digest immutability ⇒ `attested == True` forever after)
  — no KMS / Rekor storm, no unbounded referrer growth.
- `knock audit` can be extended in a follow-up to a signed-vs-unsigned coverage tier once all
  paths emit attestations.
- Re-signing on predicate-schema bumps and stamping/backfilling annotations placed by another
  tool are explicitly out of scope (YAGNI, separate future concern).

Full design spec: [2026-06-15-attestation-coverage-design.md](../../superpowers/specs/2026-06-15-attestation-coverage-design.md)
