# kyverno — admission gate requiring a valid houba scan attestation (E4)

A [Kyverno](https://kyverno.io) `ClusterPolicy` that denies admission of any Pod from
the demo registry unless a **valid, signature-verified houba scan attestation** is
present in the OCI registry. This is the admission-time enforcement counterpart of the
kargo promotion gate (E1): both readers consume the same single signed referrer that
`houba attach` published at the front door.

## Known limitation — deny-only on this key-mode/kind setup (cosign v3 ⇄ Kyverno)

On the demo's key-mode/kind setup this gate **cannot verify** houba's attestations, so it
effectively **denies every demo-registry Pod**. It still demonstrates the *deny* beat (3b:
log4shell is rejected), but it cannot *admit* a validly attested image. Root cause, established
with evidence:

- houba signs with **cosign v3.1.1**; attestations land as
  `application/vnd.dev.sigstore.bundle.v0.3+json` referrers. `cosign verify-attestation`
  reads them fine — so the **kargo** promotion gate (`houba verify`) provides the *full*
  cryptographic enforcement (admits clean freight, holds unattested).
- Kyverno v1.18's **Cosign** verifier (which does key mode) does not read the v0.3 bundle →
  "no matching attestations". Its **SigstoreBundle** verifier reads the v0.3 bundle but is
  keyless-only → with a static key, "no matching signatures". No policy config bridges a
  cosign-v3 *key-signed* bundle, and cosign v3 cannot emit the legacy format.

So the demo's enforcement is carried by the kargo gate; this Kyverno gate is a deny-side
demonstration. The fix — keyless signing via an in-cluster Sigstore, which Kyverno's
SigstoreBundle verifier supports — is designed in
`docs/superpowers/specs/2026-06-25-keyless-attestations-kyverno-gate-design.md` and deferred
(it pulls in Knative + a full Sigstore stack, disproportionate to one demo beat).

The `rbac-read-attest-key.yaml` ClusterRole ships regardless: it is a real fix (Kyverno must be
able to read the key its policy references) and a prerequisite for any working version of this
gate; it makes the failure honest ("no matching attestations", the format issue) rather than an
RBAC error.

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

cosign v3.1.1 stores attestations as **OCI 1.1 referrers**, so Kyverno must look them up via
the OCI 1.1 referrers API rather than the legacy `-att` tag scheme. The flag is necessary but
not sufficient here — Kyverno's Cosign verifier still does not recognise the v0.3 *bundle*
referrer as an attestation (see the Known limitation above).

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
