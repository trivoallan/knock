## 1. Schema

- [x] 1.1 `Spec.admit: bool = False`; validator refusing `admit` on a git source; unit tests
- [x] 1.2 `make reference`

## 2. Signing

- [x] 2.1 `AttestorPort.sign` / `verify_signature`; `FakeAttestor` journals `signed`, seeds `image_signed`
- [x] 2.2 `CosignAdapter.sign` (same key args, signing-config, tls flags) and `verify_signature` (claim type `https://sigstore.dev/cosign/sign/v1`); fake-bin `sign` / `verify` scenarios; integration tests
- [x] 2.3 `reconcile_registry`: sign after attest on import and on the attestation backfill when `admit`; refuse `admit` without a signer at plan time; unit tests (signed after attest, not signed when `admit: false`, attest failure leaves unsigned, revoking `admit` deletes nothing)

## 3. Verify

- [x] 3.1 `Requirement.image_signature` (`image-signature`) in `domain/verify.py`; `verify_image` resolves it through `attestor.verify_signature`; `ConfigError` without a signer; unit tests

## 4. Docs

- [x] 4.1 ADR 0050 (amends 0041); amendment note on 0041's status
- [x] 4.2 `docs/how-to/verify-gate.md`: the `image-signature` row and the claim-type caveat
- [x] 4.3 `docs/examples/admission/`: an `admit: true` policy
