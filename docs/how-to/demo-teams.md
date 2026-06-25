---
title: "Run the two-team demo"
description: "Place two teams' images through separate kargo pipelines gated by houba verify — one clean image promotes, one vulnerable image is held, each owner-attributed."
sidebar_position: 10
---

`make demo-teams` extends the reference deployment with a folder of two
`MirrorPolicy` files ([team-platform.yaml](../examples/teams/team-platform.yaml),
[team-data.yaml](../examples/teams/team-data.yaml)), a grype scan-attach step, and
per-team kargo Warehouse → Stage pipelines all gated by the existing `houba-scan-gate`
`AnalysisTemplate`. The result is two divergent outcomes in one cluster — verifiable with
`houba verify`.

For the pattern and the reasoning behind team folders, see
[Team folders and kargo](../explanation/team-folders.md).

## Prerequisites

1. A running `make demo` cluster (installs kargo, the `houba-scan-gate` `AnalysisTemplate`, a
   Zot registry, and seeds the `upstream/debian-xz` fixture via `make seed-incident`).
2. `make cosign-keygen` has run — it writes the signing key pair used by `houba attach` and
   consumed by `houba verify --require scan-pass`.

```bash
# Bring up the reference cluster (takes a few minutes on first run)
make demo

# Generate the cosign key pair if you haven't already
make cosign-keygen
```

## Run the demo

```bash
make demo-teams
```

That's the only command. Under the hood it does four things in order:

1. **Reconcile** `docs/examples/teams/` — calls `houba reconcile` on the folder, which places:
   - `platform/busybox:1.37.0` (team-platform, `group:default/platform`)
   - `data/debian-xz:5.6.1` (team-data, `group:default/data`)
   — each with an SBOM referrer attached.
2. **Scan-attach** both repos — runs grype, produces a signed SARIF attestation per digest
   (`houba attach … --sign`), setting `io.houba.policy.severity` on every finding.
3. **Apply per-team kargo pipelines** — `kubectl apply -k deploy/components/kargo-teams/`,
   creating two Warehouse + Stage pairs, each wired to the `houba-scan-gate` `AnalysisTemplate`.
4. **Assert the contrast** — runs `houba verify` for each placed digest and exits non-zero if
   either result diverges from the expected outcome.

### Pinning the policy branch (optional)

By default the kargo pipelines git-sync from `main`. While iterating on a feature branch before
it is merged, override the reference:

```bash
make demo-teams TEAMS_POLICY_REF=tritri/my-branch
```

## Expected output

```
team-platform  platform/busybox:1.37.0    ✓ scan-pass (severity <= high)   verify PASS
team-data      data/debian-xz:5.6.1       ✗ scan-pass: 142 finding(s) at critical   verify FAIL

Contrast holds: team-platform PROMOTED / team-data HELD, each owner-attributed.
```

`team-platform` passes every gate and is promoted by kargo. `team-data` carries
[CVE-2024-3094](https://nvd.nist.gov/vuln/detail/CVE-2024-3094) (the XZ backdoor) with 142
critical findings; its gate blocks the promotion and the image is held.

## Inspect the kargo state

```bash
# Confirm both Warehouses and Stages exist
kubectl -n houba get warehouses,stages | grep -E 'platform|data'

# Tail the gate job logs for team-data
kubectl -n houba logs -l app.kubernetes.io/name=houba-scan-gate \
  --selector=team=data --tail=40
```

Open the kargo UI to see the promotion history for both pipelines side by side:

```bash
make kargo-ui
# then visit http://localhost:8090
```

## Cleanup

The per-team Warehouses and Stages use distinct names (`team-platform-*`, `team-data-*`) and
coexist with the reference pipeline. A fresh `make demo` cluster removes them automatically
along with everything else.

To remove just the per-team pipelines from a running cluster:

```bash
kubectl -n houba delete -k deploy/components/kargo-teams/
```
