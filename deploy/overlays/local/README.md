# `local` overlay — single inner-loop escape hatch (no operators)

The self-contained local overlay for iterating without ArgoCD. Runs both the **copy
path** (busybox) and the **rebuild path** (debian) against the reference policy at
[`docs/examples/reference/`](../../../docs/examples/reference/), with a throwaway
in-cluster **[Zot](https://zotregistry.dev)** as the mirror destination.

```bash
make local     # build image+glue → up stack → reconcile → bootstrap DT → publish SBOMs → blast-radius report
make dt-vulns  # trigger DT's keyless OSV (Debian) vuln mirror, then re-run `make publish-sbom`
make dt-ui     # browse Dependency-Track (the package-level blast-radius consumer)
```

No Harbor, no ExternalSecret, no CA/mirror config — everything needed to run houba
end-to-end fits in this single overlay.

houba's lineage stamp answers *which images derive from base X* (`make blast-radius`); the SPDX SBOM,
converted to CycloneDX and uploaded to Dependency-Track, answers the **package**-level question
*which images ship the vulnerable package X*. Component inventory works offline; CVE/severity
correlation needs a mirrored vuln source. `dt-bootstrap` enables DT's **keyless OSV** Debian
ecosystem; `make dt-vulns` restarts the apiserver to run the mirror (DT only mirrors on restart —
hence the data PVC, so the mirror isn't wiped). After it finishes (a few minutes, online), re-run
`make publish-sbom` to re-analyze and the CVEs show on the projects. (NVD is keyed + slow, so the
demo uses OSV; production can add an NVD API key.)

> **Heads-up — DT is RAM-hungry.** Dependency-Track hard-requires a **4 GB heap** (it refuses
> to boot below that), so the apiserver pod requests 4 Gi / limits 6 Gi. Give your kind/Docker
> VM ≥ 8 GB or the apiserver pod stays `Pending`/`OOMKilled` and `make dt-ui` finds no service.

Zot ships a **built-in web UI** (the `search` + `ui` extensions), so you can *see* what
houba pushed — browse the mirrored repos/tags and the provenance annotations on each
manifest, the stamp made visible:

```bash
make registry-ui   # port-forward svc/registry → http://localhost:8080
```

The UI is served by the registry itself (no second component, no CORS plumbing) on the
same port as the registry API; a real cluster browses its own Harbor/Zot console instead.

## The insecure-HTTP detail

The rebuilt images are **pushed by buildkit** to the throwaway Zot registry, which serves
plain HTTP. buildkitd defaults to HTTPS — but houba derives BuildKit's
`registry.insecure=true` push flag from the destination's `tls_verify=false` in the roster
([`secret-registries.yaml`](secret-registries.yaml)), the *same* primitive that makes
`regctl` copy over HTTP (`--tls disabled`). So the copy and rebuild paths share one source
of truth and the shared [`components/buildkitd`](../../components/buildkitd) is used as-is —
no overlay-local `buildkitd.toml`, no `--config` patch. (BuildKit's `registry.insecure`
covers the *push*; base images here are pulled from Docker Hub over HTTPS.)

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
