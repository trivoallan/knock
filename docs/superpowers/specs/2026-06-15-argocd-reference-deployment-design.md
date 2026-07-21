# Spec — ArgoCD reference deployment (App-of-Apps variant)

**Status:** designed (2026-06-15)
**Scope:** a documented ArgoCD **variant** of the reference deployment, alongside `overlays/prod` —
**not** the blessed path. The `kubectl apply -k` flow stays the default.

## Why

The reference deployment ([spec](2026-06-11-reference-deployment-design.md)) deliberately uses
git-sync + `kubectl apply -k` to keep **zero extra cluster dependencies**, and the product thesis
forbids any single orchestrator becoming a dependency. That stands. But teams that already run
ArgoCD want a copy-paste GitOps blueprint for knock. This spec adds one as a *variant* — it
demonstrates the App-of-Apps pattern and ships a reproducible kind demo, without promoting ArgoCD
to a requirement.

ArgoCD's role here (decision: option **D** — a documented variant): it manages the knock **install
manifests**. The **policy** front door is unchanged — policies are `MirrorPolicy` YAML consumed by
the knock CLI, not k8s manifests, so they keep arriving via the in-pod git-sync sidecar. ArgoCD does
not touch policies.

## What gets built

### File structure

```
deploy/argocd/
  root.yaml                      # the app-of-apps; parameterized ${ARGOCD_REPO_URL} ${ARGOCD_REPO_REF}
                                 # → points at apps/${ARGOCD_ENV}  (demo|prod)
  apps/
    demo/
      registry.yaml              # child Application → deploy/argocd/sources/registry
      knock.yaml                 # child Application → deploy/argocd/sources/knock-demo
    prod/
      eso.yaml                   # child Application → external-secrets Helm chart (operator)   [sync-wave 0]
      keda.yaml                  # child Application → keda Helm chart (operator)                [sync-wave 0]
      prometheus.yaml            # child Application → kube-prometheus-stack Helm chart          [sync-wave 0]
      openbao.yaml               # child Application → openbao Helm chart (secret backend)       [sync-wave 0]
      knock.yaml                 # child Application → deploy/argocd/sources/knock-prod          [sync-wave 1]
      buildkitd.yaml             # child Application → deploy/argocd/sources/buildkitd           [sync-wave 1]
  sources/
    registry/kustomization.yaml      # registry:2 only (reuses ../../overlays/local-lite/registry.yaml)
    knock-demo/kustomization.yaml    # ../../base + secret + copy-path config, WITHOUT the bundled registry
    knock-prod/kustomization.yaml    # ../../base + externalsecret + ClusterSecretStore (→ openbao) + image +
                                     #   BUILDKIT_HOST in config; NO buildkitd/keda components (sibling apps),
                                     #   NO seed (the seed is a demo-only `bao kv put`, never a committed manifest)
    buildkitd/kustomization.yaml     # buildkitd workload + knock's autoscaling config — references the existing
                                     #   ../../components/buildkitd/* and ../../components/keda-buildkitd/*
```

- **Anti-drift:** every kustomize source references the existing `../base`,
  `../../components/buildkitd/*`, `../../components/keda-buildkitd/*`, `registry.yaml`,
  `secret-registries.yaml`, and `externalsecret.yaml` files — no copies. The one duplicated literal is
  `BUILDKIT_HOST` (a stable in-cluster DNS string; see below).
- **Demo = 2 children** (`registry` + `knock`, copy path) → real App-of-Apps mechanics. The registry
  is genuine demo infra, separate from the knock install.
- **Prod = 6 children** (`eso` + `keda` + `prometheus` operators + `openbao` secret backend, then
  `knock` core + `buildkitd` rebuild/autoscaling add-on) → the prod root bootstraps the **entire** stack
  from git, secret backend included. Still the documented **extension seam**: add a child per
  additional cluster (a second `destination`) or per additional policy domain.

### buildkitd as a separate child — how the CronJob wiring is handled

`components/buildkitd` does two things: it ships the buildkitd **workload** (Deployment / Service /
NetworkPolicy) **and** it patches the knock `CronJob` to inject one env var,
`BUILDKIT_HOST=tcp://buildkitd.knock.svc.cluster.local:1234`. Two apps cannot both write the
`CronJob`, so the split moves the wiring, not the patch:

- **buildkitd app** ships the workload only (references the three existing manifests — no copy).
- **`BUILDKIT_HOST` becomes a config literal** in `sources/knock-prod`'s `configMapGenerator`, set
  unconditionally. It is harmless on the copy path (only rebuild policies invoke `buildctl`), and the
  service DNS is deterministic. So the buildkitd app is purely **additive**: sync it → the rebuild
  path works; don't → knock runs copy-only against a host that is simply never dialed.

This is why the ArgoCD variant composes knock **à la carte** (base + per-env patch) instead of
pointing the prod child at `overlays/prod`: that overlay bundles the buildkitd and keda-buildkitd
components, which would deploy them twice. The existing `kubectl apply -k` overlays are unchanged —
they keep the self-contained, component-bundled shape. knock's **autoscaling config** (the
`keda-buildkitd` component: `ScaledObject` + `ServiceMonitor`) rides with the `buildkitd` app — it is
knock's autoscaler for the buildkitd workload, so the two belong together. The KEDA **operator** that
the `ScaledObject` needs is a separate platform app (next section).

### Bootstrapping the operators (ESO + KEDA) as children

The prod root manages the two cluster operators that knock's prod resources depend on, so the whole
stack comes up from git:

- **`eso`** — the External Secrets Operator, sourced from the upstream Helm chart
  (`https://charts.external-secrets.io`, chart `external-secrets`), namespace `external-secrets`.
- **`keda`** — KEDA, sourced from the upstream Helm chart (`https://kedacore.github.io/charts`, chart
  `keda`), namespace `keda`.
- **`prometheus`** — `kube-prometheus-stack` (`https://prometheus-community.github.io/helm-charts`),
  namespace `monitoring`. The **Prometheus Operator** flavour, because knock's autoscaling config ships
  a `ServiceMonitor` (needs the `ServiceMonitor` CRD + a Prometheus that scrapes it). Trimmed via Helm
  values to the minimum knock needs — `grafana.enabled=false`, `alertmanager.enabled=false`,
  node-exporter off — leaving the operator + a Prometheus server.
- **`openbao`** — OpenBao (`https://openbao.github.io/openbao-helm`), namespace `openbao`. The secret
  backend ESO reads. Generic / OSS (a Linux Foundation Vault fork), so it stays org-neutral; ESO drives
  it through its **`vault` provider** (API-compatible). Helm values run it in **dev/auto-unseal mode**
  for kind-demoability (known root token, in-memory) — explicitly *not* production-grade. Prod hardens
  it (real seal/unseal, k8s auth instead of root token) or repoints the `ClusterSecretStore` at the
  org's existing OpenBao/Vault/cloud SM.

All four are Helm-source `Application`s (no chart vendoring); chart `targetRevision` is **pinned** and
Renovate-trackable. Sync options: `CreateNamespace=true` and **`ServerSideApply=true`** (the operator
charts ship large CRDs that exceed the client-side apply annotation limit).

**Ordering via sync waves.** Platform apps (`eso`, `keda`, `prometheus`, `openbao`) are annotated
`argocd.argoproj.io/sync-wave: "0"`, consumer apps (`knock`, `buildkitd`) `"1"`. ArgoCD installs the
CRDs + backend first; the wave-1 `ExternalSecret`, `ClusterSecretStore`, `ScaledObject`, and
`ServiceMonitor` then resolve instead of transiently `SyncFailed` on a missing CRD/backend.

**Wiring the secret path.** `knock-prod` ships the `ClusterSecretStore` named `knock-secret-store`
(`vault` provider → the openbao Service) that the existing `externalsecret.yaml` already references. The
secret **data** is seeded by a documented demo step — a `bao kv put knock/registries
KNOCK_REGISTRIES=…` against the dev OpenBao pod (a Makefile/runbook action, **not** a committed
manifest, so the prod manifests never overwrite real creds). The `ScaledObject`'s `serverAddress`
already targets the operator's headless `prometheus-operated.monitoring.svc:9090` (release-name
independent — works as shipped with `kube-prometheus-stack`), so the `keda-buildkitd` component is
reused unchanged.

**The irreducible boundary.** With `openbao` a child, the secret *backend* is bootstrapped from git too —
the prod apps set is end-to-end runnable on kind with **no external dependency**. The one thing that
fundamentally cannot live in git is the **real credential values**: the demo seed writes placeholders;
in real prod the org writes the real registry token into OpenBao out-of-band (or federates OpenBao to
its IdP). knock ships the wiring; the secret material is seeded, never committed.

The platform/consumer children stay **prod-only** in the `make` flow: the lite kind demo keeps the fast
copy path (placeholder plain `Secret`, no operators), while the full stack (ESO + KEDA +
kube-prometheus-stack + OpenBao + rootless buildkitd) is the heavy rebuild/autoscale flavour — the prod
apps set, render-/dry-run-checked in CI and now fully runnable on kind.

### The Applications

- **root.yaml** — applied directly by `make` (or `kubectl`), the bootstrap. Points at
  `deploy/argocd/apps/${ARGOCD_ENV}` on `${ARGOCD_REPO_URL}@${ARGOCD_REPO_REF}`. `syncPolicy.automated`
  with `prune: true` + `selfHeal: true` (the GitOps point).
- **child Applications** — each `destination` = `kubernetes.default.svc` / namespace `knock` (registry
  child too — it lives in the knock namespace for the demo). `automated` sync. kustomize source.

## Demo flow & make targets

Mirrors the existing `up-*` / `demo-*` / `CLUSTER` / `image` pattern in the Makefile.

```make
make demo-argocd        # kind up → build+load knock:dev → install argo-cd → patch argocd-cm → apply root → wait sync → run + blast-radius
make demo-argocd-run    # one-shot Job from the synced CronJob (same idiom as demo-lite-run)
make down               # existing teardown
```

`demo-argocd` sequence:
1. `cluster` + `image` (reuse existing targets — kind create, build+load `knock:dev`).
2. Install argo-cd: `kubectl apply -n argocd -f <pinned upstream install.yaml>`; `kubectl wait` the
   argocd-server deployment Available.
3. **Patch `argocd-cm`** to set `kustomize.buildOptions: --load-restrictor LoadRestrictionsNone`
   (required — `base` references `scripts/blast-radius.sh` outside `deploy/`); restart/repoll the
   repo-server so it picks up the option.
4. `envsubst` over `root.yaml` (`ARGOCD_REPO_URL`/`ARGOCD_REPO_REF` default to the public repo @
   `main`, `ARGOCD_ENV=demo`) → `kubectl apply -f -`.
5. `kubectl wait` root + children `Synced`/`Healthy` → `make demo-argocd-run` → `make blast-radius`.

GitOps-pure: `make` applies **only** `root.yaml`; registry + knock arrive via ArgoCD from git.

The default kind demo is the **copy path** (`ARGOCD_ENV=demo`: registry + knock-demo) — fast and
buildkitd-free. The `buildkitd` child app lives under `apps/prod` and is render-checked in CI; running
it live on kind is the heavier rebuild flavor (rootless buildkitd already proven by `make
demo-transform`), reachable by syncing the `prod` apps set against a demo registry — documented in the
runbook, not wired into the default `demo-argocd` target.

## Prerequisites & documented ceilings

- **`--load-restrictor LoadRestrictionsNone`** is a *global* ArgoCD build option (`argocd-cm`),
  not settable per-Application. The demo patches it; for prod it is a documented cluster prerequisite.
- **ESO / KEDA / Prometheus / OpenBao are all bootstrapped by the prod root** (Helm-source children,
  sync-wave 0) — no external prerequisites remain. The only irreducible boundary is the **real
  credential values** seeded into OpenBao (cannot live in git). See "Bootstrapping the operators".
- **Fork/branch ceiling** (intrinsic App-of-Apps ↔ git coupling, not a knock shortcut): ArgoCD reads
  children **from git**. `make` parameterizes `root.yaml`, but children are pulled from
  `${ARGOCD_REPO_URL}@${ARGOCD_REPO_REF}`. To demo your branch: push it to your fork and run
  `ARGOCD_REPO_URL=… ARGOCD_REPO_REF=… make demo-argocd`. The target prints this caveat; a
  `ponytail:` comment in the Makefile names the ceiling.
- **Secrets** unchanged: demo = placeholder `Secret` (from `local-lite`), prod = the existing
  `ExternalSecret`.

## Architecture & docs sync (per CLAUDE.md)

- **Runbook:** new `## ArgoCD variant (App-of-Apps)` section in
  `docs/runbooks/reference-deployment.md` — explicitly the variant, not the blessed path.
- **ADR:** `docs/architecture/decisions/0022-argocd-reference-deployment.md` (thin, links this spec).
- **C4:** ArgoCD is a new external system + deployment node. Add to `workspace.dsl`: an `ArgoCD`
  software system and a **Deployment view `DeployArgoCD`** (root Application + children — eso, keda,
  prometheus, openbao, knock, buildkitd — syncing the stack into the cluster, with the External Secrets
  Operator, KEDA, kube-prometheus-stack, and OpenBao shown as ArgoCD-managed platform components).
  Refresh the committed Mermaid export under `docs/architecture/_export/`.
- **examples/:** *not* touched — `docs/examples/` documents `MirrorPolicy` files, not deployments.
  The "example" artifact here is `deploy/argocd/` + the runbook section. (Stated so the absence of an
  `examples/` change is intentional, not an omission.)

## Testing & CI

- **Render-check** (lightweight, added to `.github/workflows/ci.yml`):
  `kustomize build --load-restrictor LoadRestrictionsNone` over `deploy/argocd/sources/{knock-demo,
  knock-prod,registry,buildkitd}`. The `deploy/argocd/apps/{demo,prod}` dirs have **no
  `kustomization.yaml`** (ArgoCD reads them via a `directory` source), so they are not
  `kustomize build`'t — instead each `Application` YAML is parsed and asserted to be `kind:
  Application` with a pinned Helm `targetRevision` where it sources a chart. The
  `eso`/`keda`/`prometheus`/`openbao` children are Helm-source `Application`s (rendered in-cluster by
  ArgoCD, not by `kustomize build`) — the check validates the `Application` manifests are well-formed
  and their pinned chart `targetRevision` is set, not the charts' output.
- **Demo = manual/local**, not CI — installing argo-cd on kind in CI is heavy and matches the current
  posture (`make demo-lite` is not in CI). `make demo-argocd` is the runnable check.
- **No Python tests / coverage impact** — only manifests, Makefile, and docs change.

## Out of scope

- ArgoCD managing the policy repo (that was option B/C — rejected; policies stay git-sync).
- ApplicationSet / multi-cluster generators (the root is the documented seam; not built now).
- An in-cluster git server for the demo (rejected — the parameterized `repoURL` covers branch demos
  via a fork push).
