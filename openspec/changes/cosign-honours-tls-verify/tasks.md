## 1. Implementation

- [x] 1.1 Integration test: attest and verify-attestation against a `tls_verify: false` roster entry carry `--allow-insecure-registry` and `--allow-http-registry`; a TLS entry and an unmatched ref carry neither
- [x] 1.2 `CosignAdapter` takes the roster and derives the flags per subject ref via `match_registry_by_host`
- [x] 1.3 Wire `settings.registries` into `CosignAdapter` in `cli/_di.py`

## 2. Docs

- [x] 2.1 `RegistryConfig.tls_verify` description names cosign; `make reference`
- [x] 2.2 Local overlay README: cosign shares the same `tls_verify` source of truth
