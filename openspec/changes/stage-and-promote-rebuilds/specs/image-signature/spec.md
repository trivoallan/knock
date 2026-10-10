# Spec Delta

## ADDED Requirements

### Requirement: Verification with a file key uses its public half

When the signer is `key` and the configured key reference is a private key file, knock SHALL verify
attestations and image signatures with the public key derived from it. When the reference is
already a public key file, knock SHALL verify with it as is. A key from which no public key can be
derived SHALL fail the command as an adapter error, and SHALL NOT be reported as "nothing verified".
KMS and keyless verification SHALL be unchanged.

#### Scenario: Private key file

- **WHEN** the signer is `key`, the reference is a private key file, and an image carries an attestation signed with it
- **THEN** `knock verify` finds that attestation

#### Scenario: Public key file

- **WHEN** the signer is `key` and the reference is the matching public key file
- **THEN** `knock verify` finds the attestation, and no key is derived

#### Scenario: Unusable key

- **WHEN** the signer is `key` and no public key can be derived from the reference
- **THEN** the command fails with an adapter error (exit 2)

#### Scenario: KMS key

- **WHEN** the signer is `kms`
- **THEN** verification passes the KMS reference unchanged
