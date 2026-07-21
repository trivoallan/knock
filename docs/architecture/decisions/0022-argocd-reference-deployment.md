# 22. ArgoCD reference deployment (App-of-Apps variant)

Date: 2026-06-15

## Status

Superseded by [23. Single Argo reference deployment that is the demo](0023-single-argo-reference-deployment.md)
— the App-of-Apps is now the single reference (no demo/prod split; thesis-minimum operators).

Originally accepted; builds on [4. Reference deployment](0004-reference-deployment.md) and
[16. buildkitd autoscaling](0016-buildkitd-autoscaling.md).

## Context

The reference deployment (ADR 0004) deliberately uses git-sync + `kubectl apply -k` to keep zero
extra cluster dependencies, and the product thesis forbids any single orchestrator becoming a
dependency. But teams already running ArgoCD want a copy-paste GitOps blueprint, and knock's
"the front door is a merged PR" maps naturally onto App-of-Apps.

## Decision

Add an ArgoCD App-of-Apps **variant** under `deploy/argocd/`, alongside (not replacing) the overlays.
A parameterized `root.yaml` points at `apps/${ARGOCD_ENV}` (demo|prod). The demo manages two children
(registry + knock, copy path); the prod root bootstraps the **entire** stack from git — the External
Secrets Operator, KEDA, kube-prometheus-stack, and OpenBao as sync-wave-0 Helm children, then knock +
buildkitd as wave-1 consumers. buildkitd is its own additive app: its CronJob wiring becomes a
`BUILDKIT_HOST` config literal in `knock-prod`, so two apps never write the same resource. Sources are
composed à la carte from `deploy/base` + the existing `components/*` (no copies); the overlays are
untouched. ESO reads OpenBao via its `vault` provider through the `knock-secret-store`
`ClusterSecretStore`. A `make demo-argocd` target installs argo-cd on kind and syncs the demo from git.

## Consequences

- A full GitOps stack — including the secret backend — comes up from git; the prod apps set is
  end-to-end runnable on kind. The only irreducible boundary is the real credential *values* (seeded
  into OpenBao out-of-band, never committed).
- ArgoCD must set `kustomize.buildOptions: --load-restrictor LoadRestrictionsNone` (global; the demo
  patches `argocd-cm`) because `base` references `scripts/blast-radius.sh` outside `deploy/`.
- Intrinsic ceiling: ArgoCD reads children from git, so a branch demo requires a fork push
  (`ARGOCD_REPO_URL` / `_REF`).
- OpenBao runs in **dev mode** for kind-demoability — explicitly not production-grade; prod hardens it
  or repoints the `ClusterSecretStore`. No application code, port, or adapter changes — manifests,
  Makefile, CI, and docs only.
- Approaches not taken: ArgoCD managing the policy repo (policies are not k8s manifests — git-sync
  stays); ApplicationSet/multi-cluster generators (the root is the documented seam); an in-cluster git
  server for the demo (the parameterized `repoURL` covers branch demos).

Full design spec: [2026-06-15-argocd-reference-deployment-design.md](../../superpowers/specs/2026-06-15-argocd-reference-deployment-design.md)
