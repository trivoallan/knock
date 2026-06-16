# Transforms & signed attestations

## Transform vocabulary

Hardening steps are pluggable primitives: `injectCA`, `rewritePackageSources`, and `setTimezone`
(e.g. `setTimezone: { zone: Europe/Paris }`). Adding a primitive is a single self-contained
compiler in `houba/domain/transforms/steps.py`.

## Signed attestations (SLSA / in-toto)

On the **rebuild path**, houba can additionally **sign** the result. Set `HOUBA_ATTEST_SIGNER` to
`keyless`, `kms`, or `key` (default `""` = off, no attestation — exactly like an empty
`HOUBA_LABEL_PREFIX` emits no labels) and ensure `cosign` is on `PATH`. Two attestations are
produced, attached to the image digest as OCI referrers:

- **`https://slsa.dev/provenance/v1`** — emitted by BuildKit (the build facts). houba only
  enables it (`--opt attest:provenance=mode=max`).
- **`https://houba.dev/predicate/transform/v1`** — houba's transform/hardening lineage
  (which policy/import/variant, the source digest, the resolved steps, the builder id),
  signed via the configured signer.

Trust is org configuration, never baked in: `keyless` uses Fulcio + an OIDC identity
(point `HOUBA_ATTEST_FULCIO_URL` at an internal CA if you run one); `kms`/`key` sign with
`HOUBA_ATTEST_KEY_REF` (a KMS URI or a key path). A blank `HOUBA_ATTEST_REKOR_URL` writes
**no transparency-log entry** — the air-gapped path. See
[`attested/redis.yml`](../examples/attested/redis.yml).

The **same signer** also covers the **`houba attach` path**: with `HOUBA_ATTEST_SIGNER` set, each
ingested scan result is attached *both* as the raw SARIF referrer *and* as a signed in-toto
attestation (`https://houba.dev/predicate/scan/v1`) over the image digest — so a downstream
admission controller can *require* a signed scan, not merely read an annotation. Pure copies (no
rebuild, no scan) stay at the annotation layer.
