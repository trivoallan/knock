# 10. Horizontal sharding (scale-out)

Date: 2026-06-12

## Status

Accepted

Builds on [9. Concurrent reconcile execution model](0009-concurrent-reconcile.md)
Extends [4. Reference deployment (kind)](0004-reference-deployment.md)

## Context

houba ran as a single CronJob, one pod reconciling all policies (`concurrencyPolicy: Forbid`) —
safe but not horizontally scalable. The threading model is the scale-up axis (parallel tags
within a pod); this is the scale-out axis (parallel policies across pods).

## Decision

Add a pure shard-selection function (`domain/sharding.py`) and a global ownership invariant
(`domain/collision.py`) so each pod deterministically owns a disjoint subset of policies; a
filter step in `reconcile_policies`, two CLI flags, and the reference CronJob becomes an Indexed
Job. They compose: a sharded pod threads the tags within its owned policies.

## Consequences

Reconcile scales out across pods with a provable no-overlap ownership invariant. Delivered in
#37.

Full design spec: [2026-06-12-horizontal-sharding-design.md](../../superpowers/specs/2026-06-12-horizontal-sharding-design.md)
