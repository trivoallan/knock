# image-signature Specification

## Purpose
TBD - created by archiving change sign-image-at-admission. Update Purpose after archive.

## Requirements

### Requirement: A policy declares admission explicitly

The `MirrorPolicy` schema SHALL carry a boolean `spec.admit`, defaulting to `false`. `admit: true`
SHALL mean that every image this policy places is admitted. The system SHALL refuse `admit: true`
on a policy whose source is a git repository (`PolicyValidationError`).

#### Scenario: Default is not admitted

- **WHEN** a policy omits `admit`
- **THEN** knock places and attests its images and signs none of them

#### Scenario: Git source refuses admit

- **WHEN** a policy with a git source declares `admit: true`
- **THEN** parsing the policy fails with a `PolicyValidationError`

### Requirement: knock signs the image of an admitted placement

When the policy is `admit: true`, the system SHALL sign the placed image (`cosign sign`) on the copy
and rebuild paths. It SHALL sign the stamped output digest, using the configured `KNOCK_ATTEST_*`
signer and signing-config, only after the SBOM and provenance attestations succeed. A signing
failure SHALL fail the operation. When the attestation backfill runs on an `admit: true` policy, the
system SHALL sign the image in the same operation.

#### Scenario: Admitted copy is signed after it is attested

- **WHEN** an `admit: true` policy imports a new tag
- **THEN** the attestor attests the output digest, then signs that same digest

#### Scenario: Non-admitted placement is attested but not signed

- **WHEN** an `admit: false` policy imports a new tag
- **THEN** the output digest is attested and never signed

#### Scenario: Attestation failure leaves the image unsigned

- **WHEN** attesting the output digest fails
- **THEN** the operation fails and no signature is placed

#### Scenario: Admit without a signer is refused

- **WHEN** a policy is `admit: true` and no `KNOCK_ATTEST_SIGNER` is configured
- **THEN** planning fails with a `ConfigError` (exit 3) before anything is placed

### Requirement: A signature is never removed from a version in service

The system SHALL NOT delete an image signature. Setting a policy from `admit: true` to `false`
SHALL stop new signatures without removing existing ones. `gc`, `purge` and reconcile deletions
SHALL touch only the referrer types they own (scan results and pending-deletion marks).

#### Scenario: Revoking admit removes nothing

- **WHEN** a policy that previously signed its images is reconciled with `admit: false`
- **THEN** no referrer is deleted and no signature call is made

### Requirement: knock verify can require the image signature

`knock verify --require image-signature` SHALL pass only when `cosign verify` returns at least one
verified claim whose `critical.type` is `https://sigstore.dev/cosign/sign/v1`. An attestation-only
digest SHALL fail, even though a bare `cosign verify` accepts it. A missing or unverifiable
signature, or unparseable output, SHALL be a gate verdict (exit 1). Failure to run cosign SHALL
exit 2. Requiring `image-signature` without a configured signer SHALL exit 3.

#### Scenario: Signed image passes

- **WHEN** the digest carries a knock image signature verifiable with the configured signer
- **THEN** `image-signature` passes

#### Scenario: Attested-only image fails

- **WHEN** the digest carries knock attestations but no image signature
- **THEN** `image-signature` fails with exit 1
