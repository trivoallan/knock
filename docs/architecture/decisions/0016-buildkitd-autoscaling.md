# 16. buildkitd autoscaling — KEDA-driven scale-up

Date: 2026-06-12

## Status

Accepted

Builds on [10. Horizontal sharding](0010-horizontal-sharding.md)

## Context

`buildkitd` runs as a `replicas: 1` Deployment — the build-path ceiling. The concurrent-reconcile
and horizontal-sharding work scaled the copy path but deliberately deferred horizontal scaling of the
build daemon (sharding ADR, decision D5). houba's reconcile is an hourly batch that issues rebuilds in
a burst, which a single `buildkitd` serialises onto one node.

## Decision

Scale `buildkitd` with a KEDA `ScaledObject` between a **warm floor of 1** and `K` replicas, driven by
a single Prometheus trigger reading `buildkitd`'s in-flight `Solve` RPC count
(`grpc_server_started_total − grpc_server_handled_total{grpc_method="Solve"}` via `--debugaddr`).
**No scale-to-zero** (the floor keeps the local build cache warm and removes the wake-before-push race
against houba's "no retry" rule), **no Cron trigger** (no schedule-drift), and **no houba application
code change** — it is a deploy/runtime concern (a new opt-in `keda-buildkitd` kustomize component,
`prod`-only; KEDA + Prometheus are documented cluster prerequisites, never embedded). `K = 1`
(component not applied) is exactly today's behaviour.

## Consequences

The build path absorbs burst load and falls back when idle, with no new state, queue, or coordinator.
The C4 Deployment view (production blueprint) gains KEDA + Prometheus infrastructure nodes driving the
`buildkitd` Deployment. **Designed, not yet implemented.** Full design + rejected alternatives:
[buildkitd autoscaling spec](../../superpowers/specs/2026-06-12-buildkitd-autoscaling-design.md).
Deferred follow-ups: registry-backed build cache (so burst replicas share the floor's cache) and
mTLS on `buildkitd` (amplified by multi-replica).
