# kyverno — admission gate requiring a valid houba scan attestation (E4)

A [Kyverno](https://kyverno.io) `ClusterPolicy` that denies admission of any Pod from
the demo registry unless a **valid, signature-verified houba scan attestation** is
present in the OCI registry. This is the admission-time enforcement counterpart of the
kargo promotion gate (E1): both readers consume the same single signed referrer that
`houba attach` published at the front door.

## What the policy does

| Aspect | Value |
|---|---|
| Matched images | `registry.houba.svc.cluster.local:5000/demo/*` |
| Predicate type | `https://houba.dev/predicate/scan/v1` |
| Signing model | KEY-mode cosign (not keyless — kind has no Fulcio/Rekor/OIDC) |
| Public key | `k8s://houba/houba-attest-key` (`cosign.pub` entry) |
| OCI referrer mode | OCI 1.1 (`cosignOCI11: true` — cosign v3.1.1 writes referrers by default) |
| Failure action | `Enforce` — deny the Pod if the attestation is absent or invalid |

The scope is intentionally narrow: only images under the demo registry prefix are
checked, so the policy never blocks Kyverno's own components or any other cluster
workload.

## Why KEY-mode cosign (not keyless)

The policy **verifies** the attestation's signature, so it references only the
**public** key (`cosign.pub`) from the `houba-attest-key` Secret — the same Secret the
scan-attach Job signs with (mounting `cosign.key`). kind has no Fulcio/Rekor/OIDC, so
keyless verification cannot work here. Kyverno skips the Rekor tlog check automatically
in key mode (air-gapped-friendly). See [`components/attest-key`](../attest-key/README.md).

## Why `cosignOCI11: true`

cosign v2+ (this demo uses v3.1.1) stores attestations as **OCI 1.1 referrers** by
default. Kyverno must look them up via the OCI 1.1 referrers API rather than the
legacy `-att` tag scheme. Without this flag Kyverno would silently find no attestation
and, under `Enforce`, deny every pod regardless of what was signed.

## Pinned to Kyverno v1.18.1 (chart 3.8.1)

The policy uses the `kyverno.io/v1` API version, with `verifyImages[*].attestations[*].type`
(not the deprecated `predicateType`) and `attestors[*].entries[*].keys.publicKeys`
(with the `k8s://` protocol), as confirmed by `kubectl explain clusterpolicy` on
Kyverno v1.18.1.

## Prerequisites (documented, not embedded)

This Component assumes the cluster already has:

- **Kyverno** (`kyverno.io/v1`) — ClusterPolicy CRD + admission webhook controller.
  Install: `helm install kyverno kyverno/kyverno --namespace kyverno --create-namespace`.
- **Secret `houba-attest-key`** in namespace `houba` — created by `make cosign-keygen`
  (contains `cosign.key`, `cosign.pub`, and `COSIGN_PASSWORD`). The policy reads only
  `cosign.pub` from this Secret.

Same posture as KEDA and the External Secrets Operator: the operator/CRDs are a cluster
prerequisite, never bundled into this Component.

## Deferred to the end-to-end demo (Task 5)

The full **"pod denied"** assertion — running a Pod whose image lacks (or has an invalid)
scan attestation and observing Kyverno reject it — needs the running demo stack (registry
+ placed, signed images) and is exercised in the e2e step, not here. This Component
ships the *manifests*; the e2e step proves the *behaviour*.
