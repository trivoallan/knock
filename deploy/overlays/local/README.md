# `local` overlay — single inner-loop escape hatch (no operators)

The self-contained local overlay for iterating without ArgoCD. Runs both the **copy
path** (busybox) and the **rebuild path** (debian) against the reference policy at
[`docs/examples/reference/`](../../../docs/examples/reference/), with a throwaway
in-cluster `registry:2` as the mirror destination.

```bash
make local   # build image → up stack → one reconcile → blast-radius report
```

No Harbor, no ExternalSecret, no CA/mirror config — everything needed to run houba
end-to-end fits in this single overlay.

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

The in-cluster `git-sync` clones `POLICY_REPO_REF` (default `main`), so the `reference/`
examples are only visible once merged. To try them from a feature branch, add
`POLICY_REPO_REF=<branch>` to the `houba-config` generator in `kustomization.yaml` and
revert before merging.

## Docker Hub rate limits

The rebuild pulls the source image (`debian`) from Docker Hub. Anonymous pulls are
rate-limited; if a run fails with `toomanyrequests` / `429`, authenticate the source with a
Docker Hub username + access token:

```bash
DOCKER_USER=<user> DOCKER_PASS=<token> make docker-auth   # seeds the optional houba-docker-config secret
make local
```

`docker-auth` builds an **inline-auth** Docker `config.json` from those vars — portable, unlike
copying `~/.docker/config.json`, which under Docker Desktop holds only a keychain reference
(`credsStore`) and no usable in-cluster credentials. It is opt-in and base-wide: both the copy
path (regctl) and the rebuild path (buildctl) read the mounted config. Without the secret,
pulls stay anonymous.
