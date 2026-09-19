## Why

knock signs **attestations** (provenance, SBOM, scan) on every image it places, but never signs
**the image**: `CosignAdapter` only runs `cosign attest` and `cosign verify-attestation`. So every
image knock places reads as unsigned to a registry UI or an admission check. We saw this on
2026-09-19 in a kind environment with Zot: every image showed "unsigned", including the ones knock
had placed.

ADR 0041 left the image signature to Kyverno ("the image's own cosign signature is Kyverno's job").
That leaves a gap. Kyverno can *check* a signature, but nothing in the chain *places* one, and a
registry that only serves signed images (Harbor's content trust on a project, for example) has
nothing to check. A signature is a durable, portable claim anyone can check. If knock placed one,
"this digest was let in" would become a fact an enforcer can read, alongside what knock already
publishes.

The signature must not be placed on every image, though. An attestation describes what happened,
and it is true of any image, admitted or not. A signature is a statement of admission. Signing
everything knock places would make the signature mean "knock touched it", which is what the stamp
already says.

## What Changes

- **New policy field `spec.admit`** (boolean, default `false`). `admit: true` says that everything
  this policy places is admitted, so knock signs the image. The flag is explicit and opt-in. The
  reasons are in `design.md`.
- **knock signs the image at placement** (`cosign sign`) on the copy and rebuild paths when the
  policy is `admit: true`. It signs the stamped output digest, and only after the provenance and
  SBOM attestations have succeeded: admission is the last thing knock does. It uses the same
  `KNOCK_ATTEST_*` signer (`keyless` / `kms` / `key`) and the same signing-config, and it honours
  the roster's `tls_verify` (from `cosign-honours-tls-verify`).
- **Backfill rides the attestation backfill.** When knock backfills a missing provenance
  attestation on an `admit: true` policy, it signs the image in the same operation.
- **A signature is never removed.** knock never deletes an image signature from a digest. Setting
  `admit` back to `false` stops *new* signatures but leaves existing ones in place. `gc` only
  collects scan-result referrers, and `purge` only deletes a tag plus its pending-deletion mark.
- **`admit: true` without a signer is refused** when the policy is planned (`ConfigError`, exit 3).
  Otherwise knock would place admitted images unsigned without saying so.
- **`admit` is refused on a git source.** The skill placement path does not sign images, and a
  field that looks like it signs but does nothing is refused, not ignored.
- **`knock verify --require image-signature`** is a new requirement alongside `stamp`, `sbom` and
  `scan-pass`. It runs `cosign verify` and passes only when a verified claim has type
  `https://sigstore.dev/cosign/sign/v1`. See the design for why presence, and even a bare
  `cosign verify` exit 0, is not enough.
- **ADR 0050 amends ADR 0041.** The stamp row's "the image's own cosign signature is Kyverno's job"
  becomes: knock *places* the image signature at admission, and Kyverno (or Harbor) *enforces* it.
  0041's decision (the read-side `verify` verb) stands, so this is an amendment, not a
  supersession.

## Impact

- Schema: `Spec.admit` in `knock/domain/mirror_policy.py`, plus a validator refusing it on a git
  source. Regenerate `docs/reference/` with `make reference`.
- Ports: `AttestorPort` gains `sign(subject_ref)` and `verify_signature(subject_ref) -> bool`.
  Per ADR 0041, sign and verify are the two halves of one cosign trust tool, so there is no new
  port.
- Adapters: `CosignAdapter.sign` and `CosignAdapter.verify_signature`, plus a `sign`/`verify`
  branch in the `tests/fake-bins/cosign` fake-bin.
- Use cases: `reconcile_registry` (sign after attest, refuse `admit` without a signer) and
  `verify` (the new requirement).
- Domain: `Requirement.image_signature` in `domain/verify.py`.
- Docs: ADR 0050, an amendment note on ADR 0041, `docs/how-to/verify-gate.md`, and the
  `admission/` example.
- No new external system and no new C4 actor. cosign is already the signer, and Kyverno and Harbor
  are already the enforcers.
