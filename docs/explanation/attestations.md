---
title: "Transforms & signed attestations"
description: "The hardening primitives and the SLSA / in-toto signing model."
sidebar_position: 3
---

## Transform vocabulary

Hardening steps are pluggable primitives: `injectCA`, `rewritePackageSources`, and `setTimezone`
(e.g. `setTimezone: { zone: Europe/Paris }`). Adding a primitive is a single self-contained
compiler in `knock/domain/transforms/steps.py`.

## Signed attestations (SLSA / in-toto)

On the **rebuild path**, knock can additionally **sign** the result. Set `KNOCK_ATTEST_SIGNER` to
`keyless`, `kms`, or `key` (default `""` = off, no attestation — exactly like an empty
`KNOCK_LABEL_PREFIX` emits no labels) and ensure `cosign` is on `PATH`. Two attestations are
produced, attached to the image digest as OCI referrers:

- **`https://slsa.dev/provenance/v1`** — emitted by BuildKit (the build facts). knock only
  enables it (`--opt attest:provenance=mode=max`).
- **`https://knock.dev/predicate/transform/v1`** — knock's transform/hardening lineage
  (which policy/import/variant, the source digest, the resolved steps, the builder id),
  signed via the configured signer.

Trust is org configuration, never baked in: `keyless` uses Fulcio + an OIDC identity
(point `KNOCK_ATTEST_FULCIO_URL` at an internal CA if you run one); `kms`/`key` sign with
`KNOCK_ATTEST_KEY_REF` (a KMS URI or a key path). A blank `KNOCK_ATTEST_REKOR_URL` writes
**no transparency-log entry** — the air-gapped path. See
[`attested/redis.yml`](../examples/attested/redis.yml).

The **same signer** also covers the **`knock attach` path**: with `KNOCK_ATTEST_SIGNER` set, each
ingested scan result is attached *both* as the raw SARIF referrer *and* as a signed in-toto
attestation (`https://knock.dev/predicate/scan/v1`) over the image digest — so a downstream
admission controller can *require* a signed scan, not merely read an annotation. Pure copies (no
rebuild, no scan) stay at the annotation layer.

The **same signer** also covers the **SBOM** on every placed image: with `KNOCK_ATTEST_SIGNER` set,
each attached SBOM is *also* emitted as a signed in-toto attestation over the image digest, with the
canonical predicate type (`https://spdx.dev/Document` / `https://cyclonedx.org/bom`) — so a downstream
gate can `cosign verify-attestation --type spdxjson` and require a trustworthy SBOM, not merely read
the raw referrer. Presence is unconditional; this signed twin is the trust tier. See
[Package-level SBOM](sbom.md#presence-then-trust).
