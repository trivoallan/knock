# 9. Concurrent reconcile execution model

Date: 2026-06-12

## Status

Accepted

Builds on [3. Reconcile output & resilience](0003-reconcile-output-contract.md)

## Context

The reconcile path was fully sequential — `reconcile_policies` loops over policies →
destinations → variants → tags — yet every expensive step is I/O (registry inspect/list, and
especially `build_and_push`, minutes per image). The work is anticipatory: no measured latency
pain today, but the concurrency boundary should be placed correctly now.

## Decision

Introduce a bounded concurrency model that respects the hexagon: a small DAG per plan,
continue-and-collect failure semantics, a thread-safe `Reporter` journal, gated by one config
var + one CLI flag. The domain stays pure; concurrency lives in the use-case layer.

## Consequences

Tags/operations within a pod run in parallel (the **scale-up** axis), bounded and deterministic
in reporting. Delivered in #37.

Full design spec: [2026-06-12-concurrent-reconcile-design.md](../../superpowers/specs/2026-06-12-concurrent-reconcile-design.md)
