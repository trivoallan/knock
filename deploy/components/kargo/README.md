# kargo — promotion gate via `houba verify` (E1)

A [kargo](https://kargo.io) pipeline whose promotion to **prod** is gated by `houba verify`,
turning houba's **signed scan attestation** into a binary promotion gate. This is the first
enforcement lever placed *in the delivery path*: an image cannot reach prod unless its scan is
present, fresh, signature-verified, and free of critical findings.

## What the four resources do

| Resource | Role |
|---|---|
| `warehouse.yaml` | Polls the demo registry repo (`registry.houba.svc.cluster.local:5000/demo/debian`) every 30s and produces digest-bound **Freight**. |
| `stage-dev.yaml` | Entry Stage; requests Freight directly from the Warehouse, no verification. |
| `stage-prod.yaml` | Sources Freight **from dev** and runs the gate as a **verification** before the Freight may settle. Passes the freight's resolved digest as `image-ref`. |
| `analysistemplate-scan-gate.yaml` | Argo Rollouts `AnalysisTemplate` (`houba-scan-gate`) that runs `houba verify <digest> --require=scan-pass --max-severity=critical --max-age=7d` as a one-shot Job. Exit 0 promotes; exit 1 holds. |

## Why KEY-mode cosign (not keyless)

The gate **verifies** the attestation's signature, so it mounts only the **public** key
(`cosign.pub`) from the `houba-attest-key` Secret — the same Secret the scan-attach Job signs
with (it mounts `cosign.key`). kind has no Fulcio/Rekor/OIDC, so keyless verification cannot work
here; the gate therefore sets `HOUBA_ATTEST_SIGNER=key` / `HOUBA_ATTEST_KEY_REF=/attest/cosign.pub`
(the tlog check is skipped automatically in key mode — air-gapped-friendly). See
[`components/attest-key`](../attest-key/README.md).

## Digest-bound, never tag-based

The Stage builds `image-ref` from the Freight with kargo's
`imageFrom(repoURL).RepoURL + "@" + imageFrom(repoURL).Digest` expression, so the gate always
verifies the exact digest being promoted.

## Prerequisites (documented, not embedded)

This Component assumes the cluster already has:

- **kargo** (`kargo.akuity.io/v1alpha1`) — Warehouse / Stage CRDs + controller. kargo's
  chart depends on **cert-manager** CRDs being present first.
- **Argo Rollouts** (`argoproj.io/v1alpha1` `AnalysisTemplate`) — kargo's verification runs
  through the Rollouts AnalysisRun machinery.

Same posture as KEDA and the External Secrets Operator: the operator/CRDs are a cluster
prerequisite, never bundled into this Component.

## Container image

The gate container image is `houba`, rewritten by the kustomize `images:` transformer (the same
local-image trick the base Jobs use) — `houba:dev` loaded into kind for the demos, a pinned
`ghcr.io` tag in prod.

## Deferred to the end-to-end demo (Task 5)

The full **"freight held"** assertion — placing a signed image, letting the Warehouse produce
Freight, and observing prod hold a freight whose scan is absent / stale / critical — needs the
running demo stack (registry + placed, signed images) and is exercised in the e2e step, not here.
This Component ships the *manifests*; the e2e step proves the *behaviour*.
