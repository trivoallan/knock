# `local-transform` demo — self-contained rebuild path without Harbor

**Status:** approved (design)
**Date:** 2026-06-12
**Related:** [`2026-06-11-image-transform-hardening-design.md`](2026-06-11-image-transform-hardening-design.md) (the transform engine), the `#29` reference deployment (`deploy/`).

## Problem

The reference deployment ships two demo tiers and they sit at opposite ends of a wide gap:

- **`local-lite`** — copy path only, into a throwaway in-cluster `registry:2` (anonymous HTTP). Fast, fully self-contained, no buildkitd. It never exercises a transform.
- **`local-full`** — the rebuild path: buildkitd, `injectCA` + `rewritePackageSources`, pushing to a Harbor that the operator installs separately, and requiring org config (`HOUBA_TRANSFORM_CA_CERTS`, `HOUBA_TRANSFORM_PACKAGE_MIRRORS`).

There is **no lightweight way to see a transform actually run**. The moment a policy carries a `transform:` block, `reconcile` dispatches through `_build_variant(builder=…)` (buildkit) instead of `registry.copy` (`houba/use_cases/reconcile.py:206`), so transforms cannot run on the copy-only `local-lite` stack. Demonstrating one currently means standing up Harbor and supplying CA/mirror config — too much friction for "show me the rebuild + stamp story".

## Goal

Add a third tier, **`local-transform`**, that runs the **rebuild path** (buildkitd) but stays **self-contained** — the same throwaway `registry:2` as lite, **no Harbor, no ExternalSecret, no CA/mirror config**. It demonstrates a real, effective transformation, the **per-variant `suffix` feature** (one source tag fanned out into regional variants), and the provenance stamps + blast-radius that follow.

### Where it sits

| Tier | Path | Destination registry | Transforms | Org config |
|---|---|---|---|---|
| `local-lite` | copy | `registry:2` HTTP (throwaway) | — | none |
| **`local-transform` (new)** | **rebuild (buildkitd)** | **`registry:2` HTTP (throwaway)** | **`setTimezone`** | **none** |
| `local-full` | rebuild (buildkitd) | Harbor (TLS, separate) | `injectCA` + `rewritePackageSources` | CA + mirror |

## Non-goals

- No change to the transform engine, the `reconcile` use case, or the buildkit adapter.
- No change to `local-lite` or `local-full`.
- No Harbor, no TLS, no org-specific config at this tier.
- Not a production posture — like lite, it is a single-node demo convenience.

## Design

### Image & transform

- **Base image:** `debian:bookworm-slim`. Verified to ship `/usr/share/zoneinfo` (so `setTimezone` is *effective*, not merely stamped), ~75 MB, and provides the `sh`/`ln`/`echo` the rendered fragment needs. `America/New_York` and `Europe/Paris` are both in its bundled tzdata.
- **Transform:** `setTimezone: { zone: <tz> }` — the only built-in step with **no external resource dependency** (`injectCA` needs CA certs, `rewritePackageSources` needs mirrors; both are org config). Its fragment (for the Europe variant) is:
  ```
  RUN ln -snf /usr/share/zoneinfo/Europe/Paris /etc/localtime && echo Europe/Paris > /etc/timezone
  ENV TZ=Europe/Paris
  ```

### New example — `docs/examples/timezone/debian.yml` (variants + suffix)

This example does double duty: it shows the rebuild path **and** the per-variant `suffix` feature. A single source tag (`bookworm-slim`) is fanned out into **two regional variants**, each with its own `setTimezone` and `suffix`. Both variants rebuild from the *same* source digest, so they share one `base.digest` but carry different `transform.version` — the blast-radius report shows **2 images → 1 `base.digest`**:

```yaml
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata:
  name: debian-tz
  labels:
    team: platform
spec:
  artifactType: image
  source:
    registry: docker.io
    repository: library/debian
  imports:
    - name: slim
      tags:
        semverOnly: false          # bookworm-slim is not a semver tag
        includeRegex: "^bookworm-slim$"
      variants:
        - name: europe
          suffix: "-europe"
          transform:
            - setTimezone: { zone: Europe/Paris }
        - name: us
          suffix: "-us"
          transform:
            - setTimezone: { zone: America/New_York }
      destinations:
        - project: demo
          repository: debian
```

Produces `demo/debian:bookworm-slim-europe` and `demo/debian:bookworm-slim-us`. (Per `houba/domain/variants.py`, an explicit variant uses its own `transform`; the suffix is applied to every output tag and alias of that variant during reconcile.) It must validate against the published policy JSON Schema (same gate as the other examples).

### New overlay — `deploy/overlays/local-transform/`

Composition = **lite's registry plumbing + full's rebuild engine**:

- `kustomization.yaml`
  - `namespace: houba`
  - `resources: [../../base, registry.yaml, secret-registries.yaml]`
  - `components: [../../components/buildkitd]` (brings the buildkitd Deployment + Service + the `BUILDKIT_HOST` patch, same as `local-full`)
  - `patches: [patch-suspend.yaml, patch-buildkitd-insecure.yaml]`
  - `configMapGenerator` (merge) overriding `houba-config`:
    - `POLICY_DIR=/policies/current/docs/examples/timezone`
    - `BLAST_REPOS=demo/debian`
  - `configMapGenerator` for the buildkitd config (`buildkitd.toml`, see below)
- `registry.yaml`, `secret-registries.yaml`, `patch-suspend.yaml` — copied verbatim from `local-lite` (each overlay already owns its own copy of `secret-registries.yaml`, so this matches the existing pattern and avoids kustomize load-restrictor issues with cross-overlay file references).

### The one hard part — buildkit pushing to a plain-HTTP registry

The buildkit adapter emits `--output=type=image,name=…,push=true` with **no** `registry.insecure` flag (`houba/adapters/buildkit_cli.py:41`), and the shared buildkitd Deployment mounts **no config**, so buildkitd defaults to HTTPS. Pushing the rebuilt image to `registry.houba.svc.cluster.local:5000` (anonymous HTTP) would fail with an HTTP-vs-HTTPS error.

**Decision (chosen): overlay-local buildkitd config.** Mark the in-cluster registry as plain HTTP in a `buildkitd.toml` that lives **only in this overlay**:

```toml
[registry."registry.houba.svc.cluster.local:5000"]
  http = true
```

Delivered as a `configMapGenerator` (`buildkitd-config`) and mounted by `patch-buildkitd-insecure.yaml` at `/etc/buildkit` — buildkitd reads `/etc/buildkit/buildkitd.toml` **by default**, so no `--config` arg and no change to the container's `args` are required. The patch is a strategic merge that appends a volume and a volumeMount (both keyed by `name`), and kustomize's name-reference transformer rewrites the volume's `configMap.name` to the hashed generator name:

```yaml
# patch-buildkitd-insecure.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: buildkitd
spec:
  template:
    spec:
      containers:
        - name: buildkitd
          volumeMounts:
            - name: buildkitd-config
              mountPath: /etc/buildkit
              readOnly: true
      volumes:
        - name: buildkitd-config
          configMap:
            name: buildkitd-config
```

This keeps the **shared `components/buildkitd` primitive generic** — the demo registry's hostname stays in the overlay, never hardcoded into the reusable component (CLAUDE.md: "org-specific hardening must become *configuration* of generic primitives").

**Rejected alternatives:**
- **(B) Put `http = true` in the shared `components/buildkitd`.** Simpler (no overlay patch) but bakes a demo hostname into the generic component — violates the no-hardcoding rule.
- **(C) TLS-terminate `registry:2` with a self-signed cert and give buildkitd the CA.** More production-like but reintroduces exactly the cert plumbing this tier exists to avoid.
- **(D) Refactor the rebuild path to `buildkit → OCI tarball → regctl push`.** Would sidestep insecure config entirely, but changes the buildkit adapter's contract and would ripple into `local-full` — out of scope.

### Makefile

New targets mirroring the lite ones, with a longer timeout (rebuild + image pull) and a readiness wait on buildkitd; plus reuse of `blast-radius`, parameterised by overlay:

```make
up-transform: cluster image ## Bring up the transform stack (buildkitd, no Harbor)
	$(KUSTOMIZE) deploy/overlays/local-transform | $(KUBECTL) apply -f -
	$(KUBECTL) -n $(NS) rollout status deploy/buildkitd --timeout=180s

demo-transform: up-transform demo-transform-run ## Rebuild stack + one reconcile + report
	@sleep 3
	$(MAKE) blast-radius OVERLAY=deploy/overlays/local-transform

demo-transform-run: ## Fire a one-shot rebuild reconcile
	-$(KUBECTL) -n $(NS) delete job houba-reconcile-run --ignore-not-found
	$(KUBECTL) -n $(NS) create job houba-reconcile-run --from=cronjob/houba-reconcile
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-reconcile-run --timeout=600s
```

`blast-radius` gains `OVERLAY ?= deploy/overlays/local-lite` so `demo-lite` keeps its current behaviour while `demo-transform` re-applies the transform overlay. `.PHONY` updated with the three new targets.

### Docs & architecture sync (CLAUDE.md conventions)

- **Overlay README** `deploy/overlays/local-transform/README.md` — what it is, the lite/transform/full positioning, and the insecure-HTTP note.
- **Examples** — update `docs/examples/README.md` with the `timezone/debian.yml` walkthrough: the copy ↔ rebuild contrast against `busybox`, and the variant/`suffix` fan-out (`-europe` / `-us`) as the first worked example of variants in the examples set.
- **C4 model — unchanged, and that is deliberate.** The intermediate tier introduces no new actor, external system, or integration: buildkitd (rebuild engine) and the in-cluster registry already exist in the model. `workspace.dsl` describes context/landscape, not deployment-overlay packaging, so it does not drift. (Noted here to satisfy the "spec that shifts architecture must update C4" gate — this spec does not shift it.)

## Testing & verification

This tier is manifests + one example policy; there is no new application code, so verification is operational plus the existing schema gate:

1. **Schema** — `docs/examples/timezone/debian.yml` validates against the published policy JSON Schema (same check the other examples pass).
2. **Kustomize build** — `kustomize build deploy/overlays/local-transform` renders without error; the rendered buildkitd Deployment mounts `buildkitd-config` at `/etc/buildkit`.
3. **End-to-end** — `make demo-transform`:
   - `houba-reconcile-run` Job reaches `Complete` (the rebuild + push to the HTTP registry succeeds — proves the `buildkitd.toml` `http = true` took effect).
   - Both variant tags exist: `demo/debian:bookworm-slim-europe` and `demo/debian:bookworm-slim-us` (proves suffix application).
   - Each rebuilt image carries the stamps: `…transform.steps` includes `setTimezone`, `…transform.version` is set, `…base.digest` equals the source digest — and the two variants share the **same** `base.digest` but differ in `transform.version`.
   - `docker run --rm demo/debian:bookworm-slim-europe date` shows CEST/CET (`Europe/Paris`) and `…-us date` shows EST/EDT (`America/New_York`) — the transforms are **effective**, not just stamped.
   - The blast-radius report lists `demo/debian` grouping both variant tags under a single `base.digest`.

### Pre-merge verification caveat

`git-sync` in the base CronJob clones `POLICY_REPO_REF` (default `main`) from `POLICY_REPO_URL`, so the deployed demo only sees `docs/examples/timezone/` **once it is on `main`**. To run `make demo-transform` from the feature branch before merge, override the ref in the overlay's `houba-config` `configMapGenerator` (`POLICY_REPO_REF=<feature-branch>`) — and revert it (or drop the override) before merging so the tier tracks `main` like the others. This is a verification-time concern only, not part of the shipped overlay.

## Risks

- **buildkit egress** — buildkitd must pull `debian` `FROM docker.io` (HTTPS, default config) and push to the in-cluster registry (HTTP, via the overlay toml). Same network assumptions lite already relies on for its docker.io pulls.
- **Rootless buildkitd resource use** — first build pulls debian layers; the 600 s reconcile timeout accommodates it. buildkit caches layers, so the second tag is fast.
- **Shared kind cluster** — if a user runs `demo-lite` then `demo-transform` on the same cluster, both push to the same `registry:2`; `demo/busybox` and `demo/debian` coexist without conflict.
