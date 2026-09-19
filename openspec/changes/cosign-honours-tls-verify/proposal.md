## Why

A roster entry with `"tls_verify": false` is honoured by regctl (`registry set … --tls disabled`),
BuildKit (`registry.insecure=true`) and syft (`insecure-use-http`), but not by cosign. Against a
plain-HTTP registry (the local kind overlay's `registry:2`, observed on 2026-09-19 with
`ghcr.io/trivoallan/knock:0.9.3`, `KNOCK_ATTEST_SIGNER=key`), `cosign attest` dials HTTPS and fails
with `http: server gave HTTP response to HTTPS client`. The copy succeeds, the attestation does not,
and every operation is reported failed.

## What Changes

- `CosignAdapter` receives the registry roster and, when the subject ref's registry matches an entry
  with `tls_verify: false`, passes `--allow-insecure-registry --allow-http-registry` to
  `cosign attest` and `cosign verify-attestation`.
- The match reuses `match_registry_by_host` (the same host resolution `attach` already uses), so
  `tls_verify` stays the single source of truth — no new setting, no new env var.
- Default unchanged: `tls_verify` defaults to `true`, and a ref matching no roster entry (or an entry
  with `tls_verify: true`) gets no extra flags.
- `RegistryConfig.tls_verify`'s description (and the generated reference) and the local overlay
  README name cosign alongside regctl and BuildKit.

## Impact

- Code: `knock/adapters/cosign_cli.py`, `knock/cli/_di.py`, `knock/config.py` (description only).
- Ports: none — `AttestorPort` is unchanged; the roster is adapter construction config.
- Docs: `docs/reference/` (regenerated), `deploy/overlays/local/README.md`.
