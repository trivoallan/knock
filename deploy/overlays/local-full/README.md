# `local-full` overlay — rebuild path + Harbor

The realistic demo layer: it exercises houba's **hardening rebuild** (inject a CA,
rewrite package sources) and pushes into **Harbor**, then stamps the result.

It is intentionally heavier than `local-lite`. Two things are *not* baked into the
manifests and must be provided:

## 1. Harbor

Harbor is installed separately (its Helm chart, several pods + persistence) — `make
demo-full` does this for you, or:

```sh
helm repo add harbor https://helm.goharbor.io
helm install harbor harbor/harbor -n houba \
  --set expose.type=clusterIP --set externalURL=https://harbor.houba.svc.cluster.local
```

Then, in the Harbor UI/API: create the **`hardened` project** and a **`robot$houba`**
account with push rights, and paste its token into `secret-registries.yaml`
(`REPLACE_ME`).

## 2. The internal CA

`corp-root.pem` here is a **throwaway demo self-signed CA** (no private key retained),
present only so `injectCA` has a valid PEM to add to the image trust store. Replace it
with your real internal root CA before this means anything.

## What runs

`POLICY_DIR` points at [`docs/examples/hardened`](../../../docs/examples/hardened): redis
`7.2.x`, rebuilt with `injectCA: {certs: [corp]}` + `rewritePackageSources: {mirror: corp}`,
pushed to `hardened/redis`. `buildkitd` (the [buildkitd component](../../components/buildkitd))
runs the rebuild; the package mirror is set to a public Debian mirror so the step is
exercised without an internal one.

> The CronJob is suspended (on-demand). Fire a run with `make demo-full-run`, then
> `make blast-radius` to see the stamp on the hardened image.
