# Single Argo reference deployment that is the demo

Status: approved (brainstorming) · Date: 2026-06-15

## Problem

The deployment/demo surface has grown to **six overlapping entry points**:

- three local overlays — `local-lite` (copy), `local-full` (rebuild + Harbor), `local-transform` (rebuild, no Harbor);
- a standalone `overlays/prod` (operators assumed pre-installed);
- an Argo `demo` app set (`ENV=demo`);
- an Argo `prod` app set (`ENV=prod`) that already brings up the full operator stack on kind end-to-end.

`make argocd-prod` on kind is *already* nearly the whole demo: the same App-of-Apps you would run in production, with throwaway credentials and registry. Everything else is redundancy that drifts, and the Makefile carries ~22 targets to drive it.

The product thesis (CLAUDE.md line 1) is that houba is a **stamper, not a mirror** — yet the blessed demo (`busybox`) exercises only the copy path.

## Decisions

1. **Argo is the single reference *and* the demo**, with one thin local escape hatch retained for inner-loop development on the manifests (the App-of-Apps reads children from git, so uncommitted changes are invisible until pushed — the escape hatch covers that gap). The three local overlays and the standalone prod overlay collapse.
2. **The reference policy demonstrates both paths** — one reconcile over a curated policy directory holding a copy entry (`busybox`) *and* a rebuild/stamp entry (`debian` `setTimezone` variants). The blast-radius report then shows copy and stamped artifacts together.
3. **The reference brings up the thesis-minimum operators** — ESO + OpenBao (the secret path) + buildkitd (rebuild). KEDA + Prometheus are a `prod-scale` pair serving autoscaling/metrics, not the demo narrative (the blast-radius consumer reads OCI annotations via a Job, not Prometheus); they remain on disk as a documented optional component, unwired by default.
4. **(Point A)** the rebuild entry stays `setTimezone` (already proven by `local-transform`, zero new infra). `injectCA` — the real thesis hardening, self-contained with a throwaway CA, no Harbor needed — is documented as an enhancement, not in the critical path.
5. **(Point B)** the `busybox/` and `timezone/` example directories are **relocated** into `docs/examples/reference/` (no duplication); README links updated.

## Target architecture — two artifacts

### Artifact 1 — `deploy/argocd/` : the reference (= the demo)

One App-of-Apps, **no demo/prod ENV split**. `root.yaml` drops the `ARGOCD_ENV` parameter; `path` becomes `deploy/argocd/apps`. The app set is:

- wave 0: `eso`, `openbao`
- wave 1: `houba` (→ `sources/houba`), `buildkitd` (→ `sources/buildkitd`)

The throwaway `registry:2` is applied out-of-band by `make demo` (unmanaged by Argo, as `argocd-prod` does today). KEDA + Prometheus apps are removed from the set.

On kind this *is* the demo. To adopt in a real cluster: override `repoURL`/`targetRevision`, point ESO at your vault, use your registry, point `POLICY_REPO_URL`/`POLICY_DIR` at your policy repo.

### Artifact 2 — `deploy/overlays/local/` : the inner-loop escape hatch

A single kustomize overlay: `base` + `components/buildkitd` + a plain registries Secret + a throwaway `registry:2` + the buildkitd-insecure patch + the CronJob-suspend patch (reconcile is fired on demand, as the old demos did), **no operators**. Driven by `kubectl apply -k` so it renders local, uncommitted manifests. This is the merged successor of `local-lite`/`local-full`/`local-transform` (essentially `local-transform` plus the copy entry). It is **not a second demo** — it is the dev path (`make local`).

## Reference policy — `docs/examples/reference/`

Two policies, loaded in one reconcile (the loader walks a directory):

- `busybox.yml` — copy, `includeRegex` + moving-tag aliases → `demo/busybox`
- `debian-tz.yml` — rebuild, `setTimezone` `eu`/`us` variants (self-contained) → `demo/debian`

Config wiring:

- `POLICY_DIR` → `…/docs/examples/reference`
- `BLAST_REPOS` → `demo/busybox demo/debian`

## Makefile surface (~22 → ~10)

Keep / introduce:

- `make demo` — the Argo reference on kind: `cluster` + `image` + `argocd` + apply `root.yaml` + seed OpenBao + out-of-band registry + wait + reconcile + blast-radius report. (Former `argocd-prod` minus KEDA/Prometheus; `argocd-seed` folded in.)
- `make demo-run` — re-fire the reconcile.
- `make local` — escape hatch: `apply -k overlays/local` + reconcile + report. Fast, no Argo, no operators.
- `make blast-radius`, `make logs`, `make down`, `make docker-auth` — unchanged.
- internal: `cluster`, `image`, `argocd`.

Delete: `up-lite`/`demo-lite`/`demo-lite-run`, `up-full`/`demo-full`/`demo-full-run`, `up-transform`/`demo-transform`/`demo-transform-run`, `demo-argocd`/`demo-argocd-run`, `argocd-prod`, `argocd-seed` (folded), and the `ARGOCD_ENV` parameter.

## File-level change inventory

**Delete**

- `deploy/overlays/local-lite/`, `deploy/overlays/local-full/`, `deploy/overlays/local-transform/` (content folds into `overlays/local`)
- `deploy/overlays/prod/` — `externalsecret.yaml` moves into the Argo source first
- `deploy/argocd/apps/demo/` (whole set), `deploy/argocd/apps/prod/keda.yaml`, `deploy/argocd/apps/prod/prometheus.yaml`
- `deploy/argocd/sources/houba-demo/`
- `docs/examples/busybox/`, `docs/examples/timezone/` (relocated)

**Add**

- `deploy/overlays/local/` (merged overlay)
- `docs/examples/reference/busybox.yml`, `docs/examples/reference/debian-tz.yml` (relocated content)
- `docs/architecture/decisions/00NN-single-argo-reference-deployment.md` (next ADR number, ~0022)

**Modify / move**

- `Makefile` — collapse targets as above
- `deploy/argocd/root.yaml` — drop `ARGOCD_ENV`; `path: deploy/argocd/apps`
- `deploy/argocd/apps/prod/{eso,openbao,houba,buildkitd}.yaml` → `deploy/argocd/apps/` (flatten); `houba.yaml` repoints to `sources/houba`
- `deploy/argocd/sources/houba-prod/` → `deploy/argocd/sources/houba/`; absorb `externalsecret.yaml`; `POLICY_DIR`/`BLAST_REPOS` → reference policy
- `deploy/base/kustomization.yaml` — `POLICY_DIR` → reference, `BLAST_REPOS` → `demo/busybox demo/debian`
- `deploy/components/keda-buildkitd/` — keep, document as optional (unwired)
- `docs/runbooks/reference-deployment.md` — rewrite around `make demo` / `make local`
- `docs/examples/README.md` — reframe around the reference policy; keep the other examples as standalone feature docs
- `docs/architecture/workspace.dsl` — collapse the per-example Deployment views (lite/full/transform/argocd/prod) into one reference Deployment view (plus, optionally, the local escape hatch)
- `docs/architecture/_export/` — regenerate the Mermaid exports
- `docs/architecture/README.md` — update the deployment-views narrative
- `docs/roadmap.md` — note the surface reduction if relevant

## Out of scope (deliberately not done)

- No KEDA/Prometheus in the default path (documented optional component).
- No Harbor in the demo (rebuild = self-contained `setTimezone`; `injectCA` is a documented enhancement).
- **No product feature is removed** — only redundant demo wiring. The `hardened`, `attested`, `retention`, `scan`, `pending-deletion` examples remain as feature documentation.

## Verification

- `make demo` on a clean kind cluster: operators sync, ESO materializes the registries Secret from OpenBao, the reconcile copies `busybox` and rebuilds+stamps `debian` variants, blast-radius reports both grouped by `base.digest` + `owner.team`.
- `make local` on a clean kind cluster: same reconcile result without Argo/operators, reflecting uncommitted manifests.
- `uv run pytest`, `ruff check`, `ruff format --check`, `mypy houba` stay green (deployment-only change, but the policy relocation must not break any test that references example paths).
- C4 model renders; `_export/` regenerated; ADR linked from the workspace Decisions pane.
