# Dependency-Track in the reference deployment — design

Date: 2026-06-16
Status: Approved (brainstorm)

## Goal

The reference deployment must demonstrate the **package-level blast-radius loop**
end-to-end with a *real* observability-stack consumer, not just the lineage-level toy
(`blast-radius.sh`). Concretely:

> knock rebuilds an image → buildkit attaches an SPDX SBOM → Dependency-Track (DT)
> ingests it → an operator answers *"which images ship the vulnerable package X?"* in DT.

DT is the org's concrete instance of the roadmap's abstract "observability stack" /
"vuln platform" consumer (ADR 0032). It is **off-the-shelf software wired in by demo
glue** — it is *not* a knock feature.

### Non-goals (YAGNI)

- No knock `DependencyTrack` adapter / use case / port. knock core is untouched.
- No change to knock's SBOM format (buildkit-native SPDX stays).
- No re-implemented DT query CLI (`make blast-radius-dt`). DT's UI/API is the query surface.
- No production-grade DT (external Postgres, HA, TLS, SSO). Demo footprint only.
- No air-gapped vuln-feed seeding. The online-feed requirement is documented, not solved.
- No continuous re-publish. Publish is on-demand after reconcile, like `blast-radius.sh`.

## Constraints that shaped the design

1. **DT is CycloneDX-only.** SPDX support was dropped in the DT v4.x line. knock emits
   SPDX (buildkit's native syft scanner). → the glue **must convert SPDX → CycloneDX**
   before upload. This is the one genuinely hard part of the integration.
2. **Both targets, reduced footprint.** DT runs in *both* `DeployReference` (cluster
   blueprint) and `DeployLocal` (kind/laptop). DT is heavy (JVM apiserver + frontend +
   normally Postgres), so the demo runs it with an **embedded H2 database** and a low JVM
   heap. One packaging, reused in both targets.
3. **The portable-stamp thesis (ADR 0032).** DT must never be modeled as an abstract
   external system in the Context/Container/Landscape C4 views. It *may* appear in the
   **Deployment** views — those are worked examples and already name concrete tools (kind,
   openbao, eso). ADR 0035 records this refinement.
4. **No knock core change** ⇒ no Pydantic model change ⇒ no `make reference` regen, no
   coverage-gate impact. The entire change lives in `deploy/`, `scripts/`, `docs/`.

## Architecture

### Topology (mirrors the existing `buildkitd` pattern)

DT joins the App-of-Apps exactly as `buildkitd` does — a component dir holding the
workload manifests, an ArgoCD source referencing them, and an ArgoCD `Application`:

- `deploy/components/dependency-track/`
  - `deployment-apiserver.yaml` — DT API server. **Embedded H2** (`ALPINE_DATABASE_MODE`
    left at the H2 default), low JVM heap (e.g. `EXTRA_JAVA_OPTIONS=-Xmx1g`).
    `# ponytail: H2 + low heap for the demo; production swaps in Postgres + TLS`.
  - `deployment-frontend.yaml` — DT frontend, pointed at the apiserver service.
  - `service.yaml` — ClusterIP services for apiserver (`8080`) and frontend (`8080`).
  - `configmap.yaml` — non-secret DT env (CORS, base URL).
  - `networkpolicy.yaml` — same posture as the buildkitd NetworkPolicy.
  - `kustomization.yaml`.
- `deploy/argocd/sources/dependency-track/kustomization.yaml` — references the component
  manifests (one source of truth), `namespace: knock`.
- `deploy/argocd/apps/dependency-track.yaml` — `Application` `knock-dependency-track`,
  `sync-wave: "1"` (an infra dependency, like buildkitd), automated sync.

### The publish glue — SPDX → CycloneDX → DT

The reference *producer-side* twin of `blast-radius.sh`. Generic, stock tooling, no
knock coupling:

- `scripts/publish-sbom.sh` — canonical, runnable standalone (same contract as
  `blast-radius.sh`: reads `KNOCK_REGISTRIES` + `BLAST_REPOS`, walks the same repos).
  For each image: `regctl` pulls the attached **SPDX SBOM attestation** →
  **`syft convert` SPDX→CycloneDX** (syft is the same engine buildkit uses — the most
  faithful converter) → `curl -X POST /api/v1/bom` to DT with the project name set to the
  image ref. Images with no SBOM attestation (copy-only, not rebuilt) are skipped + logged
  (same "coverage gap" semantics as `blast-radius.sh`).
- `deploy/base/job-publish-sbom.yaml` — twin of `job-blast-radius.yaml`. Mounts the script
  via a configMap added in `deploy/base/kustomization.yaml`
  (`publish-sbom.sh=../../scripts/publish-sbom.sh`), reads `KNOCK_REGISTRIES`, `BLAST_REPOS`,
  and the DT API key Secret.

**Container packaging.** The knock runtime image is *not* bloated with a demo-only
converter. The publish step is a chain of init/main containers using **stock images** over
a shared `emptyDir`:

1. init `knock` (has regctl + python3): pull the SPDX attestation → `/work/<ref>.spdx.json`.
2. init `anchore/syft`: `syft convert` each SPDX → `/work/<ref>.cdx.json`.
3. main `curlimages/curl`: `POST` each CycloneDX to DT with the API key.

`# ponytail: stock images, no glue image to build`. (If the single-script-in-one-container
symmetry of `blast-radius.sh` is preferred later, fold the three tools into one small glue
image — deferred; not worth a build artifact now.)

### API-key bootstrap (the one fiddly piece)

DT requires an API key with `BOM_UPLOAD` + `PROJECT_CREATION` to accept uploads, and its
default `admin/admin` forces a password change on first login. A one-shot bootstrap closes
this:

- `scripts/dt-bootstrap.sh` + `deploy/base/job-dt-bootstrap.yaml`:
  1. Wait for the DT API to be ready (init container poll with timeout).
  2. `POST /api/v1/user/login` as `admin/admin`; on forced change, set a demo password.
  3. Create (or fetch) an API key for a team with `BOM_UPLOAD` + `PROJECT_CREATION`.
  4. Write the key into a k8s Secret `dt-api-key` in the `knock` namespace.
- RBAC: a dedicated ServiceAccount with `create`/`patch` on `secrets` in `knock`.
- Ordering via ArgoCD **sync-waves**: DT (wave 1) → bootstrap (wave 2) → publish runs after
  reconcile, reading `dt-api-key`.

### Demo loop

`make local` gains two steps and a pointer:

```
build → up → reconcile → dt-bootstrap → publish-sbom → blast-radius (lineage, kept)
                                                      ↘ port-forward to the DT UI
```

- New `make publish-sbom` target (and the bootstrap folded into `make local`).
- The lineage-level `make blast-radius` report is **kept** — it shows the stamp-only layer;
  DT shows the package layer. The two adjacent layers are the point.

### Honest offline boundary (documented, not engineered)

- The **component-inventory** query ("which images contain `log4j-core 2.14`?") works
  **offline** with no vuln feed — and that *is* the blast-radius value.
- **CVE/severity correlation** requires DT to have downloaded the NVD feeds (online, slow on
  first boot). The walkthrough states this rather than promising air-gapped correlation.

## Error handling / failure modes

Consistent with the house "no retry" stance:

- Failed upload → the publish Job fails; ArgoCD re-syncs. No in-script retry.
- DT not ready → the bootstrap/publish init container times out and fails loudly.
- Image without an SBOM attestation (copy-only path) → skipped + logged, not an error
  (mirrors the `blast-radius.sh` coverage-gap line).

## Testing

The glue is bash and lives outside knock core. `blast-radius.sh` has **no test** (verified),
so this stays at **parity**:

- Validated end-to-end by `make local` running the full loop.
- **No new pytest.** (If a smoke test is later wanted, it would run `publish-sbom.sh`
  against `regctl`/`syft`/`curl` fake-bins asserting a CycloneDX POST — but only once
  `blast-radius.sh` gains an equivalent, to keep the demo scripts symmetric.)

knock core is untouched, so the existing coverage gates (≥80 % global, ≥90 % `domain`) are
unaffected.

## Docs & C4 obligations (CLAUDE.md)

Landed in the same change:

- **ADR 0035** — "Dependency-Track is the worked-example currency consumer." Refines ADR
  0032: DT may be named in **Deployment** views (worked examples); the abstract
  Context/Container model stays generic.
- `docs/architecture/workspace.dsl` — add the DT instance + the publish Job to the
  **DeployReference** and **DeployLocal** deployment views. Refresh the committed Mermaid
  exports under `docs/architecture/_export/`.
- `docs/architecture/README.md` — deploy-view rationale update.
- `deploy/overlays/local/README.md` — walkthrough updated with the bootstrap → publish →
  DT-UI steps and the offline-feed caveat.
- `docs/roadmap.md` — note that the reference deployment now *demonstrates* the loop closure
  via an off-the-shelf consumer, while currency/continuous-correlation remains **out of
  knock's product scope** (no contradiction with the "out of scope" entries — the demo wires
  a third-party tool, knock does not own it).

## File-change summary

New:
- `deploy/components/dependency-track/{deployment-apiserver,deployment-frontend,service,configmap,networkpolicy,kustomization}.yaml`
- `deploy/argocd/sources/dependency-track/kustomization.yaml`
- `deploy/argocd/apps/dependency-track.yaml`
- `deploy/base/{job-publish-sbom,job-dt-bootstrap}.yaml` (+ RBAC for the bootstrap SA)
- `scripts/{publish-sbom.sh,dt-bootstrap.sh}`
- `docs/architecture/decisions/0035-dependency-track-worked-example-consumer.md`

The App-of-Apps `root.yaml` points at `deploy/argocd/apps` and auto-discovers Application
manifests there, so the new DT app is registered just by adding the file — `root.yaml` is
**not** edited.

Edited:
- `deploy/base/kustomization.yaml` (configMaps + resources for the two Jobs)
- `Makefile` (`publish-sbom` target; fold bootstrap into `local`)
- `docs/architecture/workspace.dsl` + `docs/architecture/_export/*`
- `docs/architecture/README.md`, `deploy/overlays/local/README.md`, `docs/roadmap.md`

Untouched: all of `knock/` (no core change), `make reference` output.
