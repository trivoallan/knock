## Purpose

How knock tells its signer that a destination registry speaks plain HTTP. The roster's
`tls_verify` flag already drives regctl and BuildKit; this capability is the rule that it drives
cosign identically, so a registry reachable by one tool is reachable by all three.

## ADDED Requirements

### Requirement: Attestation signing and verification honour the roster's tls_verify

The system SHALL drive cosign from the same `tls_verify` roster flag that drives regctl and BuildKit:
when the subject reference's registry matches a `KNOCK_REGISTRIES` entry with `tls_verify: false`,
every cosign `attest` and `verify-attestation` call SHALL pass `--allow-insecure-registry` and
`--allow-http-registry`. Otherwise the system SHALL pass neither flag, so TLS remains the default.

#### Scenario: Attesting on a plain-HTTP registry

- **WHEN** knock attests `registry.local:5000/app@sha256:…` and the roster holds `registry.local:5000` with `tls_verify: false`
- **THEN** the `cosign attest` invocation includes `--allow-insecure-registry` and `--allow-http-registry`

#### Scenario: Verifying on a plain-HTTP registry

- **WHEN** `knock verify` reads the scan attestation of a digest on a registry whose roster entry has `tls_verify: false`
- **THEN** the `cosign verify-attestation` invocation includes `--allow-insecure-registry` and `--allow-http-registry`

#### Scenario: TLS registry or unknown registry keeps the default

- **WHEN** the subject's registry has `tls_verify: true` (the default) or matches no roster entry
- **THEN** no cosign invocation includes `--allow-insecure-registry` or `--allow-http-registry`
