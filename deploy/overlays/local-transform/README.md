# `local-transform` overlay — rebuild path, runnable self-contained (no Harbor)

The middle tier between [`local-lite`](../local-lite) (copy path) and
[`local-full`](../local-full) (rebuild + Harbor + org config).

It runs the **rebuild (transform) path** — buildkitd rebuilds each image through the
transform engine and stamps the result — but stays self-contained: the same throwaway
in-cluster `registry:2` as lite, **no Harbor, no ExternalSecret, no CA/mirror config**.

| Tier | Path | Destination | Transforms | Org config |
|------|------|-------------|------------|------------|
| `local-lite` | copy | registry:2 (HTTP) | — | none |
| **`local-transform`** | **rebuild** | **registry:2 (HTTP)** | **setTimezone** | **none** |
| `local-full` | rebuild | Harbor (TLS) | injectCA + rewritePackageSources | CA + mirror |

## What it demonstrates

[`docs/examples/timezone/debian.yml`](../../../docs/examples/timezone/debian.yml) mirrors
one source tag (`debian:bookworm-slim`) and fans it into two **regional variants** via the
per-variant `suffix` — `bookworm-slim-europe` (Europe/Paris) and `bookworm-slim-us`
(America/New_York). Both rebuild from the same source digest, so they share one
`base.digest` but carry different `transform.version`.

```bash
make demo-transform   # build image → up stack → one rebuild reconcile → blast-radius report
```

## The insecure-HTTP detail

The rebuilt images are **pushed by buildkit** to the throwaway `registry:2`, which serves
plain HTTP. buildkitd defaults to HTTPS, so [`buildkitd.toml`](buildkitd.toml) marks that one
registry `http = true`, [`patch-buildkitd-insecure.yaml`](patch-buildkitd-insecure.yaml) mounts
it at `/etc/buildkit`, and the kustomization appends `--config /etc/buildkit/buildkitd.toml` to
the daemon's args — the **rootless** buildkit image does *not* auto-load that path, so without the
explicit `--config` the push fails with `server gave HTTP response to HTTPS client`. All of this
lives **here**, in the overlay — the shared [`components/buildkitd`](../../components/buildkitd)
primitive stays generic.

## Running before merge

The in-cluster `git-sync` clones `POLICY_REPO_REF` (default `main`), so the `timezone/`
example is only visible once merged. To try it from a feature branch, add
`POLICY_REPO_REF=<branch>` to the `houba-config` generator in `kustomization.yaml` and
revert before merging.
