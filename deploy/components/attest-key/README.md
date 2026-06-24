# attest-key — demo cosign signing key

Key-mode cosign signing for the scan-attach Job (key-mode, **not** keyless: kind has no
Fulcio/Rekor/OIDC, so keyless verification cannot work).

There is **no kustomize Component here** because the signing wiring is not declarative: the
`HOUBA_ATTEST_SIGNER` / key mount lives in [`deploy/base/job-scan-attach.yaml`](../../base/job-scan-attach.yaml),
and the `houba-attest-key` Secret it consumes is created out-of-band by `make cosign-keygen`
(a generated demo keypair). **Private key material is NEVER committed.**

- `make cosign-keygen` generates `/tmp/houba-demo.{key,pub}` and loads Secret `houba-attest-key`
  (`cosign.key`, `cosign.pub`, empty `COSIGN_PASSWORD`).
- The scan-attach Job mounts only `cosign.key` (the private key, for signing).
- The verify side (kargo gate, Kyverno admission) mounts only `cosign.pub` (the public key).

This must run before the scan-attach Job (the Job mounts the Secret), so `make demo` calls
`cosign-keygen` before the reconcile.
