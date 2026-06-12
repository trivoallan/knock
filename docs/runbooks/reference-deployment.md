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
