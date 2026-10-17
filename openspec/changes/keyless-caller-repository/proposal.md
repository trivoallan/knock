# Proposal

## Why

knock verifies a keyless signature on two claims only: the certificate identity
(`KNOCK_ATTEST_VERIFY_IDENTITY`) and the OIDC issuer (`KNOCK_ATTEST_VERIFY_OIDC_ISSUER`). When the
signer is a GitHub *reusable* workflow, the certificate identity names the **called** workflow,
not the repository that called it. uske's reusable workflow `extra-screen.yml` signs this way, so
`knock promote` accepts an attestation produced by **any** repository that calls that workflow
(uske `RISK-09`, accepted until knock can bind the caller). Fulcio already writes the caller in
the certificate's "GitHub Workflow Repository" extension, and cosign checks it with
`--certificate-github-workflow-repository`; knock only has to expose it.

## What Changes

- New setting `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY` (`owner/name`). When set, every keyless
  verification also passes `--certificate-github-workflow-repository <value>` to cosign: the
  promotion's attestation and signature checks (`knock promote`) and the `knock verify` gate.
  Empty, behaviour is unchanged.
- Setting it with a key or KMS signer is refused at startup with a configuration error: a key
  signature carries no GitHub certificate, so the binding would silently check nothing.
- `docs/how-to/verify-gate.md` corrected: without an identity, cosign does not "apply its default
  check" — keyless verification fails, so knock fails closed. The page documents the new setting.
- Not in scope: binding the caller's ref, trigger or SHA (`--certificate-github-workflow-ref` and
  siblings), a generic claim map, or raw extra cosign arguments. Rejected: a claim map adds
  validation and documentation for needs nobody has stated; raw arguments could also weaken the
  check. GitLab is not covered: its certificate identity already names the calling pipeline's
  configuration.

## Capabilities

### New Capabilities

- `keyless-verification`: what knock requires of a keyless signature or attestation before it
  counts — identity, issuer, and, when configured, the GitHub repository that ran the signing
  workflow — and how a configuration that cannot be checked is refused.

### Modified Capabilities

<!-- none: image-signature and the promotion keep their requirements; they gain a stricter
     verification through the new capability -->

## Impact

- Code: `knock/config.py` (new field on the attestation settings, validator against `key`/`kms`),
  `knock/adapters/cosign_cli.py` (`_verify_args`), their tests; `docs/reference/configuration.md`
  and `config.schema.json` regenerated; `docs/how-to/verify-gate.md`.
- Callers: uske's `extra-screen.yml` will pass `-e KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY=<caller>`
  once a knock release carries it (follow-up change in uske, which closes `RISK-09`).
- No breaking change: the setting is optional and empty by default.
