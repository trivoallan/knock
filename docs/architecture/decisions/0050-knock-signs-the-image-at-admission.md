# 50. knock signs the image at admission

Date: 2026-09-19

## Status

Proposed.

Amends [41. `knock verify` — read-side gate over knock's referrers](0041-knock-verify-read-side-gate.md):
the boundary that left "the image's own cosign signature" to Kyverno moves. Builds on
[15. Sign the knock attach scan referrer](0015-scan-attestation.md).

## Context

knock signs *attestations* (provenance, SBOM, scan) on every image it places, but never the image
itself: `CosignAdapter` only ran `cosign attest` / `verify-attestation`. ADR 0041 left the image
signature to Kyverno, so every knock-placed image reads as "unsigned" to a registry UI or to a
registry that serves only signed images (observed 2026-09-19 on Zot). Kyverno can *enforce* a
signature, but no one *placed* one.

A signature and an attestation do not say the same thing. An attestation records a fact that is
true of any placed image. A signature says the image was admitted. Signing everything knock places
would turn it into a second stamp.

Admission is decided outside knock today (an orchestrator derives a policy naming only the
admitted tags), so knock needs a contract for knowing that an image is admitted.

## Decision

- **`spec.admit: bool`, default `false`.** `admit: true` asserts that everything the policy places
  is admitted. It is opt-in because a signature is never removed from a version in service: if
  someone forgets the flag, an admitted image is left unsigned, which is visible and can be
  backfilled. The opposite default would sign images that were never admitted, and that cannot be
  undone. The flag is refused on a git source, and refused (`ConfigError`) when no signer is
  configured.
- **knock signs last.** It runs `cosign sign` on the stamped output digest, after the SBOM and
  provenance attestations succeed, on both the copy and rebuild paths and on the attestation
  backfill. It uses the same `KNOCK_ATTEST_*` signer and signing-config, and the roster's
  `tls_verify`.
- **A signature is never removed.** No knock path deletes one. Flipping `admit` back to `false`
  stops new signatures and removes nothing.
- **`knock verify --require image-signature`** passes only on a verified claim of type
  `https://sigstore.dev/cosign/sign/v1`. With cosign v3, a signature and an attestation are the
  same referrer type, and a bare `cosign verify` accepts an attestation-only image.
- **The boundary moves.** knock *places* the image signature. Kyverno, Harbor or `knock verify`
  *enforce* it. The rest of ADR 0041 stands.

## Consequences

- An enforcer that only asks "does `cosign verify` pass?" treats knock's attestations as
  admission. It must check the claim type, or trust a key or identity that is used only for
  admission (a second signer, which would be a configuration change).
- `admit` is a policy-level assertion, not a per-digest verdict: an update or rebuild under
  `admit: true` is signed without a new verdict. That gap closes when the gate moves into knock,
  at which point the verdict, not the policy, decides each signature.
- No new port, adapter, external system or C4 actor: `AttestorPort` gains `sign` and
  `verify_signature` on the existing cosign adapter.

Full change: [openspec/changes/sign-image-at-admission](../../../openspec/changes/sign-image-at-admission/proposal.md)
([design](../../../openspec/changes/sign-image-at-admission/design.md)).
