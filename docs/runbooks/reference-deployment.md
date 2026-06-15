# Runbook — the reference deployment

The blessed way to run houba: a Kubernetes **CronJob** that `houba reconcile`s a
git-sync'd policy repo, on a kind cluster locally and in a real cluster in prod — the
*same* manifests (`deploy/`), so the demo **is** the blueprint. Design rationale:
[the spec](../superpowers/specs/2026-06-11-reference-deployment-design.md) and the C4
[Deployment view](../architecture/workspace.dsl).

```
deploy/
  base/                       CronJob(houba) + git-sync + blast-radius Job + config
  components/buildkitd/       rebuild-path add-on (rootless buildkitd + NetworkPolicy)
  overlays/local-lite/        kind: registry:2, copy path        ← fast demo
  overlays/local-full/        kind: Harbor + rebuild path        ← realistic demo
  overlays/prod/              real registry, ExternalSecret      ← copy into your cluster
```

## Prerequisites

- `docker`, `kind`, `kubectl` on PATH.
- The houba image must bundle `regctl` + `buildctl` (the runtime `Dockerfile` does).

## Lite demo (copy path) — the 5-minute loop

```sh
make demo-lite        # create kind cluster, build+load houba:dev, apply, reconcile, report
```

What it does: stands up an in-cluster `registry:2`, fires a one-shot reconcile of
[`docs/examples/busybox`](../examples/busybox) (git-sync'd from this repo), then runs the
blast-radius consumer. Re-run pieces individually:

```sh
make demo-lite-run    # another reconcile (idempotent — unchanged tags are skipped)
make blast-radius     # re-read the stamp and print blast radius
make logs             # tail the reconcile logs
make down             # tear down the cluster
```

Expect the blast-radius report to list the mirrored busybox artifacts grouped by
`base.digest` and by `owner.team`, and to flag any artifact carrying no stamp as a
**coverage gap** (run `make blast-radius` *before* the first reconcile to see the gap,
then again after to see it close — coverage gates the value).

## Full demo (rebuild path + Harbor)

Heavier — see [`overlays/local-full/README.md`](../../deploy/overlays/local-full/README.md)
for the Harbor install, the `hardened` project + `robot$houba` token, and the (demo) CA.
Then:

```sh
make up-full
make demo-full-run    # rebuild redis through injectCA + rewritePackageSources, push, stamp
make blast-radius
```

## Production — copy the `prod` overlay

`overlays/prod` is the blueprint. To adopt:

1. Repoint `POLICY_REPO_URL` at **your** policy repo. A merged PR there is the front
   door; git-sync brings it into the pod each run.
2. Wire secrets: the [`ExternalSecret`](../../deploy/overlays/prod/externalsecret.yaml)
   pulls `HOUBA_REGISTRIES` (host + robot token) from your backend via the External
   Secrets Operator. Sealed Secrets is a drop-in alternative. **Never commit the roster
   with credentials.**
3. Set the published image tag (`images:` in the overlay kustomization).
4. The CronJob runs hourly (no `suspend`); adjust `schedule` as needed.

```sh
kubectl kustomize --load-restrictor LoadRestrictionsNone deploy/overlays/prod | kubectl apply -f -
```

> The `--load-restrictor` flag is needed because the blast-radius `configMapGenerator`
> references the canonical `scripts/blast-radius.sh` (kept outside `deploy/` so it is also
> runnable standalone against the examples). `kubectl apply -k` cannot pass the flag, so
> render-then-apply.

## ArgoCD variant (App-of-Apps) — optional

A GitOps **variant** for teams already running ArgoCD. It is **not** the blessed path —
`kubectl apply -k` above stays the default. Manifests live in `deploy/argocd/`:

```
deploy/argocd/
  root.yaml            the app-of-apps (parameterized: ARGOCD_REPO_URL / _REF / _ENV)
  apps/demo/           registry + houba (copy path)            ← the kind demo
  apps/prod/           eso + keda + prometheus + openbao (operators, wave 0)
                       + houba + buildkitd (consumers, wave 1) ← bootstraps the whole stack
  sources/             à-la-carte kustomize (base + components/*, no copies)
```

The prod root bootstraps the **entire** stack from git: the External Secrets Operator,
KEDA, kube-prometheus-stack, and OpenBao (the secret backend) as sync-wave-0 Helm children,
then houba + buildkitd as wave-1 consumers. The only thing not in git is the real credential
*values* (seeded into OpenBao out-of-band).

### Kind demo (copy path)

```sh
make demo-argocd      # kind up → install argo-cd → apply root → sync from git → reconcile → report
make demo-argocd-run  # another one-shot reconcile from the synced CronJob
make down             # tear down
```

`make` applies **only** `root.yaml`; ArgoCD pulls the `registry` + `houba` children from
git and syncs them. The demo installs argo-cd and patches `argocd-cm` with
`kustomize.buildOptions: --load-restrictor LoadRestrictionsNone` (a global build option,
required because `base` references `scripts/blast-radius.sh` outside `deploy/`; ArgoCD has no
per-Application equivalent).

> **Branch ceiling.** ArgoCD reads the child Applications **from git**, so the demo reflects
> what is *pushed*, not local edits. To demo your branch, push it to your fork and run
> `ARGOCD_REPO_URL=https://github.com/you/houba ARGOCD_REPO_REF=your-branch make demo-argocd`.

### Kind: bring up the full prod stack

```sh
make argocd-prod      # kind + argo-cd, then sync the `prod` apps set and seed dev OpenBao
make argocd-seed      # (re)seed OpenBao on its own, once the pod is Running
```

`argocd-prod` applies the **prod** App-of-Apps and brings up all four platform operators
(ESO + KEDA + kube-prometheus-stack + OpenBao) then houba + buildkitd, and seeds the dev
OpenBao so ESO can resolve `houba-registries`.

> **What this shows — and doesn't.** It demonstrates the GitOps **bootstrap** (the whole
> stack, secret path included, coming up from git). It is **not** a live mirror on kind: the
> `prod` source targets org placeholders — `POLICY_REPO_URL=gitlab.example.com`, the published
> `ghcr.io/trivoallan/houba` image, and a seeded roster pointing at an in-cluster registry the
> `prod` apps set does not deploy. Point `sources/houba-prod` at your policy repo + registry
> (next section) for a working reconcile.

### Production

`apps/prod/` is the blueprint. To adopt:

1. Copy `root.yaml`, hardcode your `repoURL` / `targetRevision`, set `ARGOCD_ENV=prod`,
   `kubectl apply` it. ArgoCD brings up the four platform operators then houba + buildkitd.
2. Point `sources/houba-prod` at **your** policy repo (the `POLICY_REPO_URL` config) and
   pinned image.
3. **Secrets:** the prod root bootstraps OpenBao in **dev mode** (kind-demoable only). The two
   demo-only glue steps below wire ESO to it (never committed — credential *values* stay out of
   git); `make argocd-seed` runs exactly these:
   ```sh
   # (a) the token ESO authenticates with — dev root token is "root"
   kubectl -n openbao create secret generic openbao-token --from-literal=token=root
   # (b) seed the registry roster ESO will materialize (placeholder for the demo).
   #     Select the pod by label (the chart's server is a StatefulSet, not a Deployment).
   kubectl -n openbao exec -i \
     "$(kubectl -n openbao get pod -l app.kubernetes.io/name=openbao -o jsonpath='{.items[0].metadata.name}')" -- \
     sh -c 'BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=root bao kv put secret/houba/registries HOUBA_REGISTRIES='"'"'{"local":{"host":"registry.houba.svc.cluster.local:5000","tls_verify":false}}'"'"''
   ```
   For real prod, harden OpenBao (seal/unseal + Kubernetes auth, dropping the static token) or
   repoint the `ClusterSecretStore` (`sources/houba-prod/clustersecretstore.yaml`) at your
   existing OpenBao / Vault / cloud SM, and write the real registry token the same way.
4. **Prometheus** is bootstrapped (kube-prometheus-stack), so KEDA autoscaling is
   self-contained — no external monitoring stack required.

> Each operator ships large CRDs; the children use `ServerSideApply=true`. Sync waves order
> the install (operators' CRDs before the `ExternalSecret` / `ScaledObject` / `ServiceMonitor`
> that need them).

## Horizontal sharding (optional)

houba scales out by **policy ownership**: each pod reconciles a disjoint subset of policies, so no two
pods ever write the same destination repository (a global invariant forbids two policies sharing a repo).

To shard across N pods, run the reconcile CronJob as an **Indexed Job**: set both `completions: N` and the
`SHARD_COUNT` ConfigMap value to N (they must match), and optionally `parallelism: M` (M ≤ N) to cap
concurrent pods — useful because the build path is bounded by `buildkitd` capacity. Kubernetes injects
`JOB_COMPLETION_INDEX` per pod; houba receives it as `--shard-index`. `N = 1` (the base default) reconciles
every policy in one pod, exactly as before.

> Build throughput is capped by `buildkitd`. Scaling the build path means scaling buildkitd — the
> opt-in autoscaling below does exactly that.

## buildkitd autoscaling (optional, prod)

The `prod` overlay can autoscale `buildkitd` from a **warm floor of 1** to `K` replicas under build
load, via the [`keda-buildkitd`](../../deploy/components/keda-buildkitd) component (already referenced
by `overlays/prod`). Design: [ADR 0016](../architecture/decisions/0016-buildkitd-autoscaling.md) /
[the autoscaling spec](../superpowers/specs/2026-06-12-buildkitd-autoscaling-design.md).

**Cluster prerequisites** (documented, not installed by houba — same posture as the External Secrets
Operator):

- **KEDA** — `helm install keda kedacore/keda -n keda --create-namespace`.
- **Prometheus** scraping `buildkitd:6060` — the component ships a `ServiceMonitor` (Prometheus
  Operator / kube-prometheus-stack flavour). On an annotation-scrape cluster, drop the ServiceMonitor
  and add `prometheus.io/scrape: "true"` + `prometheus.io/port: "6060"` to the buildkitd pods instead.

**How it scales.** `buildkitd` runs with `--debugaddr 0.0.0.0:6060`, exposing OpenTelemetry metrics.
The KEDA `ScaledObject` reads the **`Solve` completion rate**
`sum(rate(rpc_server_call_duration_seconds_count{rpc_method=~".+/Solve"}[2m]))`: during the hourly
rebuild burst many builds complete → the rate rises → KEDA scales `1→K`; between ticks it returns to
the floor. **No scale-to-zero** (keeps the build cache warm; the Service always has an endpoint, so
houba's no-retry first connection always lands).

**Tunables** (in [`scaledobject.yaml`](../../deploy/components/keda-buildkitd/scaledobject.yaml)):
`maxReplicaCount` (`K`, the ceiling), `threshold` (target Solves/sec per replica), and
`serverAddress` (your Prometheus). Without the component, `buildkitd` stays at a single replica
(today's behaviour).

> **Note (v0.30.0):** the metric is buildkit's OTel `rpc_server_call_duration_seconds_count`, a
> *completion-rate* signal — not an in-flight gauge (buildkit exposes none). A single long build only
> registers on completion; autoscaling targets the multi-build bursts, with the warm floor covering the
> lone-build case.

> **Security:** more replicas widen the `buildkitd` surface — see the mTLS note below.

## Security posture (read before prod)

- **buildkitd is rootless** (no privileged container) but needs *unconfined*
  seccomp/AppArmor — that is the rootless trade-off, not a shortcut. Its TCP endpoint is
  **unauthenticated**: the bundled [`NetworkPolicy`](../../deploy/components/buildkitd/networkpolicy.yaml)
  restricts it to the houba pod, but for anything beyond a single-node demo add **mTLS**
  (buildkitd client certs) on top.
- **houba needs no Kubernetes API access** — its ServiceAccount has token automounting
  off. It talks to registries, not the cluster.
- **Secrets are referenced, never embedded.** The demo overlays carry placeholder/no-cred
  rosters; prod uses ExternalSecret.

## The consumption hook — plugging in a real scanner

`scripts/blast-radius.sh` is the generic, zero-lock-in consumer: regctl + python3 reading
the OCI annotations houba stamps (`org.opencontainers.image.base.digest`,
`io.houba.owner.team`, `io.houba.policy`). It is the minimal proof that **the stamp alone
computes blast radius**.

In a real deployment you point your existing stack at the *same* annotations:

- **Trivy / Grype** — scan the mirrored repos; pivot a CVE's affected base layer to
  `base.digest`, then to `owner.team`.
- **Wiz / registry webhooks** — ingest the annotations on push; index `owner.team` +
  `base.digest` for instant blast-radius queries.
- **Datadog / PowerBI / a CMDB** — periodically harvest annotations (the script's logic,
  scheduled) into your query layer.

houba does not call any of these — the coupling is the data. That is the whole point: the
label is the product.
