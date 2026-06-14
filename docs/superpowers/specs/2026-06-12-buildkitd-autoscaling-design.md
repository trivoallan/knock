# buildkitd autoscaling — KEDA-driven scale-up

- **Date:** 2026-06-12
- **Status:** implemented (2026-06-14) — manifests landed; D4 metric amended after empirical validation
- **Scope:** a KEDA `ScaledObject` driving the `buildkitd` Deployment between a warm floor of 1
  replica and `K` replicas under build load, plus the `buildkitd` change needed to expose the
  driving metric. Pure deploy/runtime: **no houba application code changes**. Implements the
  buildkitd-scaling target that the [horizontal-sharding spec](2026-06-12-horizontal-sharding-design.md)
  (decision D5) deliberately deferred.

## Context & motivation

`buildkitd` runs today as a `replicas: 1` Deployment (`deploy/components/buildkitd/deployment.yaml`),
long-running, reached by houba over a ClusterIP Service (`buildkitd:1234`). It is the **build-path
ceiling**: one daemon interleaves rebuilds up to one node's resources. The concurrent-reconcile
(scale-up, in-pod tag threading) and horizontal-sharding (scale-out, cross-pod policy sharding) specs
both scale the **copy** path immediately, but explicitly leave the build path capped at the single
`buildkitd` — its horizontal scaling is named as the target and **deferred** (sharding spec D5).

This spec is that deferred driver. houba's reconcile is an **hourly batch** (`CronJob`,
`schedule: "0 * * * *"`); when a run has rebuilds, it issues them in a **burst** (the concurrent
spec threads tags, so several `buildctl build` subprocesses run at once). A single `buildkitd`
serialises that burst onto one node. We want extra `buildkitd` replicas to absorb the burst, then
fall back when idle — without introducing state, a queue, or a coordinator (roadmap ethos: houba is
**not an operator**; the registry is the only state store).

## Goals

1. Let `buildkitd` scale from a **warm floor of 1** to `K` replicas under real build load, and back.
2. Keep houba **stateless and coordination-free** — no queue, no pushgateway, no app-side state. The
   scaling signal is read from `buildkitd` itself.
3. **No houba application code change** — the hexagon (`domain/` / `ports/` / `use_cases/`) is
   untouched. This is a deploy + `buildkitd`-config concern only.
4. `K = 1` (component not applied) must be **exactly today's behaviour** (graceful default).
5. Honour houba's **"no retry logic anywhere"** rule: `buildkitd` must always have ≥ 1 endpoint when
   houba pushes a build, so the first connection never has to wait for a wake-up.

## Non-goals

- **Scale-to-zero.** Rejected (see D1): it destroys `buildkitd`'s local build cache every cycle and
  reintroduces a wake-before-push race against the "no retry" rule. The floor stays at 1.
- **Registry-backed build cache.** Deferred (D6): with a warm floor of 1 the steady state keeps its
  local cache, so this is a throughput refinement for the burst replicas, not a correctness
  prerequisite. Future work in the `buildkit_cli` adapter.
- **Dynamic shard count / autoscaling the reconcile pods.** Out of scope and against the sharding
  model (N is a static hash partition); this spec scales only the build daemon, not houba itself.
- **Installing KEDA or Prometheus.** They are **documented cluster prerequisites** (same posture as
  External Secrets Operator in `prod`), referenced, never embedded.
- **mTLS hardening of `buildkitd`.** Already flagged in the manifest as a pre-existing follow-up;
  this spec references it (more replicas ⇒ more surface) but does not deliver it.

## Decisions (with rejected alternatives)

| # | Decision | Rejected alternatives & why |
|---|----------|------------------------------|
| D1 | **Warm floor of 1, no scale-to-zero** (`minReplicaCount: 1`). | *Scale-to-zero* (the original instinct): the build cache lives on an `emptyDir` (`/home/user/.local/share/buildkit`), so 0 replicas wipes it every hour → cold rebuilds; and a 0→1 wake-up races houba's first `buildctl` connection, which **cannot retry** (house rule). The floor removes both problems for the price of one idle daemon — which the org already runs today. |
| D2 | **Single Prometheus trigger** on the `ScaledObject`. | *KEDA Cron pre-warm trigger*: justified only when waking from 0; with a warm floor it would merely pre-scale `1→K` to anticipate the tick burst, at the cost of a recurring window that **must not drift** from houba's `schedule` (a second source of truth to keep in sync, cf. `SHARD_COUNT == completions`). Not worth it — we accept a short start-up lag at the tick instead. *CPU/memory scaler*: cannot be the sole trigger for a 0-floor and is coarse; moot here anyway since the floor handles activation. |
| D3 | **KEDA `ScaledObject`** on the existing `Deployment`. | *Raw HPA*: no clean way to read an in-flight-build metric without KEDA's Prometheus scaler; KEDA wraps HPA and adds the external trigger. *StatefulSet*: `buildkitd` replicas are interchangeable workers behind a Service — no stable identity needed. |
| D4 | **Metric = `Solve` completion *rate*** (`rate(rpc_server_call_duration_seconds_count{rpc_method=~".+/Solve"})`), via `buildkitd`'s OpenTelemetry rpc metrics. *(Amended 2026-06-14 — see "The driving metric"; the original in-flight `started−handled` count was disproven against v0.30.0.)* | *In-flight `Solve` count* (`started_total − handled_total{method="Solve"}`): the legacy grpc-go series **do not exist** on `moby/buildkit:v0.30.0` (OTel-based; no in-flight gauge) — empirically disproven, so completion-rate replaces it. *CPU as a proxy*: coarse, conflates cache I/O with build work. |
| D5 | **Opt-in component, `prod`-only**; KEDA + Prometheus as documented prerequisites. | *Bundling KEDA/Prometheus*: against the reference-deployment rule that external operators are referenced, never embedded (cf. ESO). *Enabling it in the kind overlays*: KEDA/Prometheus are usually absent in kind and the demo gains nothing from scaling — local overlays keep `buildkitd` static at 1. |
| D6 | **Registry-backed cache deferred**, not in scope. | *In-scope now*: only the burst replicas (2..K) start cold; the floor replica keeps its cache, so we never regress vs today. Defer the `--export-cache/--import-cache type=registry` change to a later `buildkit_cli` work item. |

## Architecture

### Scaling model — floor 1, Prometheus-driven

```
            scrape :6060                    queries
 buildkitd ─────────────▶ Prometheus ◀──────────────── KEDA ScaledObject
 (--debugaddr)            (prerequisite)               min=1, max=K, 1 trigger
     ▲                                                      │ sets replicas
     │ buildctl build (1 conn/build, via Service)           ▼
 houba reconcile (hourly CronJob, bursts rebuilds)     Deployment buildkitd
```

- **Floor = 1**: `buildkitd` is always warm → its local cache survives between ticks (no regression),
  the Service always has an endpoint (houba's no-retry first connection always lands), and there is
  **no wake-before-push race**.
- **Ceiling = K**: under a burst, the in-flight-`Solve` metric rises; KEDA scales `1→K`. The extra
  replicas join the Service and kube-proxy spreads new `buildctl` connections across them
  (one `buildctl build` subprocess = one gRPC connection = one build), so K replicas absorb K
  concurrent builds.
- **No Cron, no scale-to-zero** ⇒ **no schedule-drift** between houba's `0 * * * *` and any KEDA
  window, and no coordination store. The only cost is a short start-up lag at the tick while the
  metric climbs and the new pods become Ready — borne by the floor replica, acceptable because
  scaling targets the *large* runs, not sub-minute micro-bursts.

### The driving metric

`buildkitd` is started with `--debugaddr 0.0.0.0:6060`, exposing Prometheus metrics.

> **D4 validated empirically against `moby/buildkit:v0.30.0` (2026-06-14).** The original plan was
> an *in-flight* `Solve` count via `grpc_server_started_total − grpc_server_handled_total`. Those
> legacy grpc-go series **do not exist** on this binary: buildkit emits **OpenTelemetry** rpc metrics,
> and `--debugaddr /metrics` exposes only Go-runtime metrics plus, after the first build,
> `rpc_server_call_duration_seconds` (a histogram recorded on *completion*) labelled
> `rpc_method="moby.buildkit.v1.Control/Solve"`. **There is no in-flight/active gauge.** So the metric
> is amended from in-flight to **Solve completion rate** — the only available Solve signal, and a good
> proxy for the same goal (absorb the burst, fall back when idle).

The KEDA Prometheus trigger `query` is therefore:

```promql
sum(rate(rpc_server_call_duration_seconds_count{rpc_method=~".+/Solve"}[2m]))
```

During the hourly rebuild burst many `Solve` RPCs complete → the rate rises → KEDA scales `1→K`;
between ticks the rate is `0` → back to the warm floor (1). The `threshold` is the per-replica target
**Solve rate** (Solves/sec, e.g. `0.2`), so K tracks `ceil(solve_rate / threshold)` capped at
`maxReplicaCount`. Trade-off: a *single long* build only increments the counter on completion, so
mid-build the rate can read low — acceptable because scaling targets the large multi-build bursts, not
sub-build granularity (the warm floor covers the lone-build case).

### Manifests

1. **`deploy/components/buildkitd/deployment.yaml`**
   - add `--debugaddr 0.0.0.0:6060` to the args, and a `containerPort: 6060` (name `metrics`);
   - **remove `replicas: 1`** — the `ScaledObject` owns the replica count (a static `replicas` would
     fight KEDA). When the KEDA component is not applied, KEDA's absence leaves the Deployment at its
     controller default of 1 ⇒ today's behaviour (goal 4).

2. **`deploy/components/keda-buildkitd/`** (new opt-in kustomize component)
   - `scaledobject.yaml` — `scaleTargetRef` → Deployment `buildkitd`, `minReplicaCount: 1`,
     `maxReplicaCount: K`, one `prometheus` trigger with the query above;
   - `servicemonitor.yaml` (or a scrape annotation, per the cluster's Prometheus flavour) — lets
     Prometheus scrape `buildkitd:6060`.

3. **`deploy/overlays/prod/kustomization.yaml`** — reference the new component. Local overlays
   (`local-lite`, `local-full`, `local-transform`) are unchanged: `buildkitd` stays static at 1.

`K` (and the Prometheus address) live in one place (the `prod` overlay / a ConfigMap value), so
there is no second source of truth to drift.

## Code / deploy touch points

- **Modify** `deploy/components/buildkitd/deployment.yaml` — `--debugaddr`, metrics port, drop
  `replicas`.
- **Create** `deploy/components/keda-buildkitd/{kustomization,scaledobject,servicemonitor}.yaml`.
- **Modify** `deploy/overlays/prod/kustomization.yaml` — pull in the component.
- **No change** under `houba/` — `domain/`, `ports/`, `use_cases/`, `adapters/`, `cli/`, `config.py`
  are all untouched.

## C4 / examples / ADR impact

- **C4 (`docs/architecture/workspace.dsl`):** the **Deployment view** gains two `infrastructureNode`s
  — the **KEDA operator** and **Prometheus** — driving the `buildkitd` node. **System Context and
  System Landscape are unchanged**: these are deployment-infrastructure elements, not context-level
  actors/external systems (same treatment as `git-sync`, ESO, the blast-radius Job).
- **ADR:** `docs/architecture/decisions/0016-buildkitd-autoscaling.md` — a thin ADR linking to
  this spec (house convention; 0012 was taken by delegated-tag-deletion, so this lands at 0016).
- **Examples (`docs/examples/`):** **no `MirrorPolicy` change** — scaling is a runtime/deploy concern,
  not policy schema (same status as sharding).
- **Runbook (`docs/runbooks/reference-deployment.md`):** add a "buildkitd autoscaling" section — the
  KEDA + Prometheus prerequisites, the `ScaledObject`, the metric, and the mTLS caveat for multi-replica.

## Testing / verification strategy

No houba application code changes ⇒ no new unit/integration tests in the Python suite. Verification is
at the manifest and runtime level:

1. **Kustomize builds clean** — `kustomize build deploy/overlays/prod` succeeds with the component
   referenced; the local overlays still build and keep `buildkitd` static at 1.
2. **`K = 1` parity** — with the component absent, `buildkitd` resolves to a single replica (today's
   behaviour); goal 4.
3. **Runtime smoke (runbook, documented not CI):** on a KEDA + Prometheus cluster, drive a burst of
   rebuilds and observe `buildkitd` scale `1→K` then settle back to 1, with the Service spreading
   builds across replicas.
4. **Metric query** validated against the bundled `buildkitd` image (risk D4) — **done** (2026-06-14):
   v0.30.0 exposes OTel `rpc_server_call_duration_seconds_count{rpc_method=".../Solve"}`, not the
   legacy grpc-go series; the metric was amended to Solve completion rate accordingly.

## Out of scope / future work

- **Registry-backed build cache** (`--export-cache/--import-cache type=registry`) so burst replicas
  share the floor replica's cache — a `buildkit_cli` adapter change, deferred (D6).
- **mTLS on `buildkitd`** — pre-existing follow-up, amplified by multi-replica; referenced here, not
  delivered.
- **Scale-to-zero** — rejected (D1) while the cache is an `emptyDir` and houba cannot retry. Would
  become reconsiderable only atop the registry-backed cache plus a guaranteed pre-warm.
- **Autoscaling the reconcile pods / dynamic shard count** — against the static-hash sharding model;
  out of scope.
