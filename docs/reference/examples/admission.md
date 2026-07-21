---
title: "Admission gate (Kyverno)"
description: "Consumer-side Kyverno gate: admit only images with a fresh knock-signed scan attestation."
sidebar_position: 7
---

The consumer side of the [scan attestation](../../explanation/attestations.md): a Kyverno `ClusterPolicy` that admits a Pod only if every image carries a knock-signed scan attestation (`https://knock.dev/predicate/scan/v1`) whose `attested_at` is within a configured max-age. This is the freshness half of the [knock / Dependency-Track boundary](https://github.com/trivoallan/knock/blob/main/docs/architecture/decisions/0032-attach-is-scan-provenance-not-a-store.md) — the gate is **purely temporal** (age of a timestamp), never vulnerability correlation. The signed predicate exists only when `KNOCK_ATTEST_SIGNER` is set on the `knock attach` run.

Adapt three things to your environment: `imageReferences` (your front-door registry glob), `publicKeys` (knock's cosign public key), and the `-720h` window (your max-age) — also validate the Kyverno time expression against your Kyverno version. Re-attaching an old report resets `attested_at`, so keep CI honest: always scan-then-attach.

```yaml title="docs/examples/admission/require-fresh-knock-scan.yaml" file=../../examples/admission/require-fresh-knock-scan.yaml
```

Apply it: `kubectl apply -f docs/examples/admission/require-fresh-knock-scan.yaml` — requires Kyverno installed in the cluster and `KNOCK_ATTEST_SIGNER` set on the `knock attach` run that produced the scan attestation.
