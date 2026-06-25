# 42. The platform-internal scan/SBOM pipeline is incremental and reconcile-fed — not a walk, not Kargo, not a bus

Date: 2026-06-25

## Status

Accepted (reworked 2026-06-25 after a benchmark refuted the original walk-based backbone)

## Context

The platform/security team needs to run its own post-placement loop over the Harbor (~150k-image
target, >300 clusters): `regis scan` → `houba attach` the signed verdict → publish the SBOM to
Dependency-Track, for **houba-placed images only** (scope A), with the stated goal that houba becomes
the front door for **all** images.

A live `regctl` benchmark settled the shape. The per-image probe cost is **~1 s/image** because the
adapter spawns a fresh `regctl` process per call (cold TLS + auth each time — a property of houba's
"no HTTP layer"), extrapolating to **~46–115 h to walk 150k**. So a periodic full-fleet walk — the
original backbone — is non-viable regardless of enumeration source (`_catalog` was a red herring).
Conversely, "all images via the front door" means scanning **at placement** covers the fleet by
construction.

## Decision

- The backbone is **incremental and reconcile-fed**: `houba reconcile` already emits a schema'd JSON
  output whose every `Operation` carries `out_digest` (set iff applied); the **scan worklist is those
  `out_digest`s.** An enqueuer (glue) pushes them to a **durable work queue**; a **scan worker pool**
  (glue) dequeues → `regis scan` → `houba attach` → publish to DT → ack, with retry + DLQ. Parallelism
  is the throughput knob. CVE rescans = DT blast-radius re-enqueued into the same queue.
- **No periodic walk, no `_catalog`, no enumeration** in the backbone; **no Argo Events/Workflows**
  (single client → a bus/engine for one pipe is unjustified net-new infra); **no Kargo** (reserved for
  the project-team promotion gate, ADR 0041); reconcile does **not** scan inline (keeps houba ≠
  scanner).
- **The backbone requires no houba-core change** — it is deployment composition of reconcile's existing
  `out_digest` output and the existing `houba attach`. houba stays **eventing-agnostic** (emits a list;
  the fan-out is deployment glue).

## Consequences

- The `_catalog`/enumeration risk recorded earlier is **resolved by avoidance**: the backbone never
  enumerates. The per-image throughput ceiling (subprocess-per-`regctl`-call) remains, but is paid at
  placement spread over the adoption ramp + churn, never in a sweep.
- houba-core footprint is **nil for the backbone**. The `houba audit --scan` presence tier (twin of the
  `--sbom` tier, [ADR 0036](0036-audit-digest-and-sbom-tier.md)) becomes **optional**, needed only for
  an occasional insurance walk / the coverage portal.
- Lifting the per-image ceiling for a fleet-scale walk (question B — images that bypassed the front
  door) would require a persistent/pipelined registry client (an architecture change against "no HTTP
  layer"); explicitly **out of scope** and unneeded by this design.
- `workspace.dsl` is deferred to implementation (deferral recorded in the spec): the deployment delta is
  the work queue + enqueuer + scan worker pool consuming reconcile's existing output; DT, regis and the
  reconcile CronJob are already modelled.

Full design: [the spec](../../superpowers/specs/2026-06-25-platform-scan-pipeline-orchestration-design.md)
