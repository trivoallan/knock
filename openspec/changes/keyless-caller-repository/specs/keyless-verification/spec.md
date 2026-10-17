# Spec Delta

## Purpose

What knock requires of a keyless signature or attestation before it counts — on promotion and at
the `knock verify` gate — including, when configured, the GitHub repository that ran the signing
workflow, and how a configuration that cannot be checked is refused.

## ADDED Requirements

### Requirement: A keyless verification checks identity and issuer

With `KNOCK_ATTEST_SIGNER=keyless`, every verification of a signature or attestation — the
promotion of a held image and the `knock verify` gate — SHALL accept a certificate only if its
identity matches `KNOCK_ATTEST_VERIFY_IDENTITY` and its issuer equals
`KNOCK_ATTEST_VERIFY_OIDC_ISSUER`. A verification that cannot be completed SHALL count as not
verified: the system fails closed.

#### Scenario: Identity and issuer match

- **WHEN** a held image carries an attestation whose certificate identity and issuer match the
  configured values
- **THEN** the promotion accepts the attestation

#### Scenario: No identity configured

- **WHEN** `KNOCK_ATTEST_VERIFY_IDENTITY` is empty and a promotion verifies a keyless attestation
- **THEN** the attestation counts as not verified and the image is not promoted

### Requirement: A keyless verification can require the signing workflow's repository

When `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY` is set (`owner/name`), every keyless verification
SHALL also require that the certificate's GitHub workflow repository equals that value. When it is
empty, no repository is required and verification behaves as without this setting.

#### Scenario: Signed from the expected repository

- **WHEN** `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY=acme/policies` and a held image's attestation was
  signed by a run of the expected workflow started from `acme/policies`
- **THEN** the promotion accepts the attestation

#### Scenario: Same workflow, another repository

- **WHEN** `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY=acme/policies` and the attestation was signed by a
  run of the same reusable workflow started from `mallory/policies`
- **THEN** the attestation counts as not verified and the image is not promoted

#### Scenario: The verify gate applies the same rule

- **WHEN** `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY` is set and `knock verify --require
  image-signature` checks an image signed from another repository
- **THEN** the gate fails

### Requirement: A repository binding with a key signer is refused

The system SHALL refuse at startup, with a configuration error (exit 3), a configuration that sets
`KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY` while `KNOCK_ATTEST_SIGNER` is `key` or `kms`: such a
signature carries no GitHub certificate, and the binding would check nothing.

#### Scenario: Key signer with a repository binding

- **WHEN** `KNOCK_ATTEST_SIGNER=key` and `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY=acme/policies`
- **THEN** knock exits 3 with a configuration error naming both settings, before any work
