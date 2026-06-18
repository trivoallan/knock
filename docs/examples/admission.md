---
title: "Admission gate (Kyverno)"
description: "Consumer-side Kyverno gate: admit only images with a fresh houba-signed scan attestation."
sidebar_position: 7
---

The consumer side of the [scan attestation](../explanation/attestations.md): a Kyverno `ClusterPolicy` that admits a Pod only if every image carries a houba-signed scan attestation (`https://houba.dev/predicate/scan/v1`) whose `attested_at` is within a configured max-age. This is the freshness half of the [houba / Dependency-Track boundary](https://github.com/trivoallan/houba/blob/main/docs/architecture/decisions/0032-attach-is-scan-provenance-not-a-store.md) — the gate is **purely temporal** (age of a timestamp), never vulnerability correlation. The signed predicate exists only when `HOUBA_ATTEST_SIGNER` is set on the `houba attach` run.

Adapt three things to your environment: `imageReferences` (your front-door registry glob), `publicKeys` (houba's cosign public key), and the `-720h` window (your max-age) — also validate the Kyverno time expression against your Kyverno version. Re-attaching an old report resets `attested_at`, so keep CI honest: always scan-then-attach.

```yaml title="docs/examples/admission/require-fresh-houba-scan.yaml"
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-fresh-houba-scan
  annotations:
    policies.kyverno.io/title: Require a fresh houba scan attestation
    policies.kyverno.io/category: Supply Chain Security
    policies.kyverno.io/description: >-
      Admit a Pod only if every image carries a houba-signed scan attestation
      (predicate https://houba.dev/predicate/scan/v1) whose attested_at is within
      the configured max-age. Freshness/provenance only — vulnerability currency
      is Dependency-Track's job (houba ADR 0032).
spec:
  validationFailureAction: Enforce
  background: false  # image verification needs the admission/pull context; it cannot run on background scans
  rules:
    - name: scan-attestation-max-age
      match:
        any:
          - resources:
              kinds:
                - Pod
      verifyImages:
        # Scope to your front-door registry — images that entered through houba.
        - imageReferences:
            - "registry.example.internal/*"
          attestations:
            - type: https://houba.dev/predicate/scan/v1
              attestors:
                - entries:
                    - keys:
                        # Replace with houba's cosign public key (the HOUBA_ATTEST_SIGNER identity).
                        publicKeys: |-
                          -----BEGIN PUBLIC KEY-----
                          REPLACE_WITH_HOUBA_COSIGN_PUBLIC_KEY
                          -----END PUBLIC KEY-----
              conditions:
                - all:
                    # Admit only if attested_at is newer than (now - 720h = 30 days).
                    # Kyverno time filters — VALIDATE both against your Kyverno version:
                    #   (a) only the whole key is wrapped in {{ }} — field names within the
                    #       expression are bare JMESPath identifiers (e.g. attested_at), NOT each
                    #       wrapped in its own nested {{ }};
                    #   (b) time_add with a negative Go duration ('-720h') — some versions instead
                    #       want time_since(attested_at) <= '720h0m0s'.
                    # Docs: https://kyverno.io/docs/writing-policies/jmespath/
                    - key: "{{ time_after(attested_at, time_add(time_now_utc(), '-720h')) }}"
                      operator: Equals
                      value: true
```

Apply it: `kubectl apply -f docs/examples/admission/require-fresh-houba-scan.yaml` — requires Kyverno installed in the cluster and `HOUBA_ATTEST_SIGNER` set on the `houba attach` run that produced the scan attestation.
