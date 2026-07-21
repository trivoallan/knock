# Reference deployment design

**Status:** Implemented — `deploy/` (kustomize), `scripts/blast-radius.sh`, `Makefile`,
`.gitlab-ci.yml`, this runbook, and the C4 Deployment view are in place. All three overlays
`kustomize build` clean; the lite layer is validated runnable end-to-end.
**Date:** 2026-06-11
**Scope:** Define the *blessed, reproducible topology* for running knock in an organization — the
"reference deployment". One kustomize-based artifact that (a) runs the full loop locally in
[kind](https://kind.sigs.k8s.io), (b) doubles as a production blueprint, and (c) is modeled as a
C4 Deployment view. Covers the loop **end to end, through consumption** (mirror/rebuild → stamp →
blast-radius query), per the product thesis *the label is the product*.

## Problem

knock today ships a CLI (`knock reconcile <dir>`), a declarative `MirrorPolicy` schema, the copy
path, and the rebuild/hardening path. What it does **not** ship is the *missing middle*: **how you
run it for real**. There is no answer to:

- Where does it run, and what triggers it (schedule vs on-merge)?
- Where do the policies live, and how does "the front door is mandatory" become operationally true?
- How do secrets (registry creds, robot accounts, git tokens) reach it without leaking into the repo?
- Where does the privileged-ish BuildKit rebuild run?
- **Crucially:** how is the stamp *consumed*? Without the consumption march, a deployment demonstrates
  plumbing, never value. The thesis (*the label is the product*) only lands when a CVE-time
  blast-radius query is shown closing the loop.

A "reference deployment" answers all of the above as **one coherent, copyable artifact**, not prose.

## Goals & constraints

- **Three uses, one artifact, zero drift.** The same manifests must (1) run the full loop in kind for
  evaluation/demo, (2) be copied into a real cluster as a blueprint, and (3) be modeled in C4. This is
  the load-bearing constraint — it is why kustomize base+overlays is chosen over divergent
  demo/prod artifacts. Matches the repo ethos *examples must never drift from specs*.
- **Full loop through consumption.** Mirror/rebuild → stamp → a blast-radius query that reads the OCI
  annotations and answers "which images derive from base digest X / belong to team Y".
- **Generic, no org-specific references** (CLAUDE.md rule). Internal hosts, registries, mirrors, and
  credentials are *configuration of generic primitives* — never hardcoded. Secrets are referenced, never
  embedded.
- **Layered, so each layer is independently runnable** ("the three by layers"): a fast lite demo, a
  realistic full demo, and a production blueprint overlay.
- **Honest about privilege.** The rebuild path runs a real (rootless) `buildkitd`; the deployment must
  not hand-wave the security posture.

## Architecture

### Runtime spine — kind + Kubernetes CronJob (decided)

The reference runtime is a **Kubernetes CronJob** running `knock reconcile`, exercised locally via
**kind**. Rationale, weighed against the alternatives:

| Candidate | Local demo | Prod representativeness | Coupling | Maps to C4 Deployment |
|---|---|---|---|---|
| **k8s CronJob (kind)** | good | high, neutral | none | 1:1 |
| GitLab CI scheduled | poor (needs a GitLab) | high *iff* a GitLab shop | strong to GitLab | awkward |
| docker-compose + cron | excellent | low | none | weak |

k8s wins on the decisive axis — **anti-drift**: the *same* manifest set runs in kind (demo layer),
copies into a real cluster (blueprint layer), and is modeled verbatim as a Deployment view (C4 layer).
GitLab CI is kept as a **documented alternative trigger** (`.gitlab-ci.yml` example) because GitLab is
already a knock port — but it couples the reference to GitLab and is not self-contained, so it is not
the spine. docker-compose is rejected as the spine: it spawns a second artifact that drifts from prod.

### Topology (full loop)

```
   ┌──────────────────────┐   git-sync    ┌─────────────────────────┐
   │  Policy GitOps repo   │◀──────────────│  knock CronJob          │
   │  (PR = the front door)│               │  reconcile + stamp      │
   └──────────────────────┘               └───────────┬─────────────┘
                                       pull │          │ rebuild (buildkitd, rootless)
                          ┌─────────────────┘          │
                          ▼                            ▼
              ┌───────────────────────┐    ┌──────────────────────────┐
              │ Source registries     │    │ Destination registry     │
              │ (Docker Hub, Quay …)  │    │ lite : registry:2         │
              └───────────────────────┘    │ full : Harbor             │
                                           └────────────┬─────────────┘
                                                        ▼
                                          ┌──────────────────────────┐
                                          │ blast-radius Job (regctl) │
                                          │ reads OCI annotations →   │
                                          │ "derives from digest X /  │
                                          │  owned by team Y"         │
                                          │ + documented scanner hook │
                                          └──────────────────────────┘
```

### The anti-drift mechanism — kustomize base + overlays

A single `base/` plus thin overlays is what lets one artifact serve all three uses without divergence:

```
deploy/
  base/                      # CronJob(knock), buildkitd Deployment, git-sync, blast-radius Job,
                             # RBAC, the policy/secret wiring — runtime-neutral
  overlays/
    local-lite/             # kind: seeded source, dest = registry:2, fake secrets,
                             #   one-shot Job (make-triggered)        → DEMO LAYER (fast)
    local-full/             # kind: Harbor (its chart), buildkitd active, rebuild path
                             #                                        → DEMO LAYER (realistic)
    prod/                   # real registries, External Secrets, hourly CronJob
                             #                                        → BLUEPRINT LAYER
```

The local overlays swap *only* the registry target, the secret source, and the trigger cadence; the
business wiring lives in `base/` and is identical across layers. That identity is the guarantee that
the demo is the blueprint.

## Components

### 1. `base/` — the runtime-neutral core

- **CronJob `knock-reconcile`** — runs the knock runtime image, `knock reconcile /policies`. In demo
  overlays it is also exposed as a one-shot `Job` (`make demo-* run`) so the loop fires on demand.
- **git-sync sidecar** — clones/refreshes the policy repo into a shared `emptyDir` mounted at
  `/policies`. This is the GitOps mechanism: a merged PR on the policy repo is what knock reconciles —
  the operational form of "the front door is mandatory". Argo CD / Flux are noted as alternatives;
  git-sync is chosen for zero extra cluster dependencies.
- **`buildkitd` Deployment (rootless)** — drives the rebuild/hardening path. Rootless to keep the
  security posture honest; the privilege note and the seccomp/userns caveats are documented in the
  runbook, not glossed.
- **blast-radius `Job`** — runs `scripts/blast-radius.sh`: walks the destination registry with regctl,
  reads the OCI annotations, and answers the two canonical queries (by `base.digest`, by
  `io.knock.owner.team`). Generic, zero lock-in.
- **RBAC + config** — `KNOCK_*` env from a ConfigMap; the registry roster (`KNOCK_REGISTRIES`) from a
  ConfigMap + Secret split (hosts public, creds secret).

### 2. Overlays

- **`local-lite`** — dest = `registry:2` (anonymous, HTTP, `tls_verify:false`), source seeded or pulled
  from Docker Hub, secrets are throwaway literals. Copy path only — no buildkitd needed to see the loop.
  Fast and deterministic, mirrors the current `docs/examples` walkthrough but on-cluster.
- **`local-full`** — dest = **Harbor** via its Helm chart (projects + a `robot$knock` account), buildkitd
  active, the `hardened/redis.yml` rebuild policy in play. Realistic; heavier to stand up.
- **`prod`** — points at real registries; secrets via **External Secrets Operator** (Sealed Secrets noted
  as an alternative) — referenced, never embedded; CronJob on an **hourly** schedule (the 7-day
  digest-stability window makes any sub-daily cadence sufficient).

### 3. Consumption — generic blast-radius script + documented scanner hook

`scripts/blast-radius.sh` is the reference consumer: `regctl` + annotation filtering, answering
blast-radius from the stamp alone. The runbook then documents **how a real consumer plugs in** — a
Datadog / Wiz / Trivy ingest reading the same OCI annotations — so the value is shown without imposing a
tool. This keeps the reference generic (CLAUDE.md) while still closing the thesis loop.

### 4. GitLab CI — documented alternative trigger

A `.gitlab-ci.yml` example runs the *same* `knock reconcile` against the *same* policy repo on a
pipeline `schedule`, for GitLab shops that prefer it over a CronJob. Documented as a variant, not the
spine.

### 5. C4 — a Deployment view (new third view)

The model today is deliberately "one model, two views" (Landscape, Context). The reference deployment
is a genuinely new *level* of concern, so it adds a **third view**: a `deploymentEnvironment
"Reference (kind)"` placing `softwareSystemInstance`s of knock / source / destination / BuildKit /
package-mirror onto Kubernetes deployment nodes, with `infrastructureNode`s for the policy git repo,
the git-sync sidecar, and the blast-radius job. Landscape and Context are **unchanged** — no new
context-level actor/external-system/integration is introduced (the policy repo and blast-radius job are
deployment-level infrastructure, modeled as `infrastructureNode`s so they do not leak into the upper
views). `docs/architecture/README.md` is updated in the same change to describe the new view.

## Decisions locked

- **Spine:** kind + Kubernetes CronJob. GitLab CI is a documented alternative trigger; docker-compose is
  rejected as the spine.
- **Anti-drift:** one kustomize `base/` + overlays (`local-lite`, `local-full`, `prod`); demo *is* the
  blueprint.
- **Destination registry, layered:** `registry:2` for the lite demo, **Harbor** for the full/blueprint
  realism.
- **Consumer:** generic `regctl` blast-radius script **+** a documented real-scanner hook; no imposed
  tool.
- **Policies:** git-sync GitOps (Argo/Flux noted as alternatives).
- **Secrets:** plain `Secret` in demo, **External Secrets Operator** (Sealed Secrets alt.) in `prod` —
  referenced, never embedded.
- **buildkitd:** rootless Deployment; privilege posture documented, not hand-waved.
- **Cadence:** one-shot `Job` (make-triggered) in demo, hourly `CronJob` in `prod`.
- **C4:** adds a third (Deployment) view; Landscape/Context unchanged; README synced.

## Artifacts produced

- `deploy/base/` + `deploy/components/buildkitd/` + `deploy/overlays/{local-lite,local-full,prod}/` (kustomize).
- `Makefile` targets: `demo-lite`, `demo-lite-run`, `up-full`, `demo-full-run`, `blast-radius`, `down`.
- `scripts/blast-radius.sh` — the generic consumer (regctl + python3).
- `docs/runbooks/reference-deployment.md` (operate it; privilege & secrets notes; scanner-hook section).
- `.gitlab-ci.yml` example (alternative trigger).
- C4 Deployment view in `docs/architecture/workspace.dsl` + `docs/architecture/README.md` section.

The runtime image already bundles `regctl` + `buildctl` (the CLIs the code shells out to), so the
deployment references it as-is — no image change is carried by this work.

## Out of scope

- An in-cluster **operator / native fleet inventory** — the roadmap explicitly keeps runtime presence out
  of knock; the deployment stamps, the org's stack queries. The blast-radius Job is a *consumer demo*,
  not an inventory service.
- **Multi-cluster / HA topology** for buildkitd or the registry — single-node kind is the reference;
  scaling notes belong in the runbook, not the reference manifests.
- Bundling a specific **scanner/observability product** — only a documented hook, to stay generic.
- Any change to knock's **application code** — this is a deployment/packaging artifact; if a gap surfaces
  (e.g. per-registry TLS config), it is filed separately, not folded in here.
