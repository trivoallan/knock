# 43. The scan pipeline becomes a `houba scan` command group shipped as an optional extra; SBOM-publish stays a referrer-bridge

Date: 2026-06-26

## Status

Proposed (draft) — refines ADR 0042

## Context

ADR 0042 established the scan pipeline as **incremental, reconcile-fed deployment glue** requiring no
houba-core change. #188 then shipped it on Redis Streams, already cleanly split into pure decision
logic (`scripts/scan_queue.py`, unit-tested) and a thin redis-py I/O boundary
(`scripts/scan_streams.py`, integration-tested), with an operator surface (`scripts/scan-dlq.py`).

The question raised: should those scripts — plus SBOM-publish-to-Dependency-Track/GUAC — become a
first-class `houba` command group? The scripts are two populations: substrate-coupled worker
mechanics (run by the ScaledJob) and a human-invoked operator surface (`scan-dlq` triage, run
mid-incident). SBOM-publish is a separate axis that touches houba's "the referrer is the interface"
thesis.

## Decision

- **Scan pipeline → optional extra (Approach D).** Promote #188's split into houba's hexagonal layers
  behind a `QueuePort` + `RedisStreamsAdapter`, shipped as `pip install houba[scan]` — redis-py an
  **optional** dependency. **Core houba stays redis-free.** The pure module moves to
  `houba/domain/scan_queue.py` under the `≥90%` gate + `mypy --strict`. The image runs `houba scan
  worker/reaper/coverage/enqueue`; operators run `houba scan dlq …`. This **refines 0042's "no
  houba-core change"**: the cross-pod fan-out and schedules stay deployment glue, but the *worker
  logic and operator surface* now live in houba as an opt-in extra — a disciplined, documented
  reopening of "zero houba-core" gated behind the optional-dependency boundary and a `QueuePort`
  redis-leak test.
- Sequenced (D′): **Door 0** = redis:8 + redis-py 8 + RESP3 staging (server bump done, #189); **Door
  1** = the internal refactor (two-way door); **Door 2** = the public `houba scan dlq` CLI surface
  (one-way door), only after the boundary proves out.
- **SBOM publish → referrer-bridge (Approach S-C).** The OCI referrer remains houba's SBOM interface.
  The DT push stays a deployment-glue script (`publish-sbom`, rewritten bash→python); GUAC pulls (zero
  houba code); `dt-bootstrap` stays glue. **No `SbomSinkPort`** unless push-delivery becomes a
  permanent product promise.

## Consequences

- houba *contains* the scan orchestration logic (opt-in), reversing the strict "redis confined to the
  image" stance — but only behind `houba[scan]`; a default `uv sync` pulls no redis.
- The #188 decision logic comes under houba's test/type gates, pinning the three silent-failure bugs
  #188 caught. Verified along the way: the confirmed-set `attested_at` is houba's own `clock.now()`
  (cosign surfaces no signed timestamp), threaded via `ScanOutcome` rather than a port extension.
- The `QueuePort` keeps Streams specifics (consumer group, `XAUTOCLAIM`, trim floor) inside the
  adapter, leaving a second broker (SQS/NATS) *possible* without committing to it (one adapter now).
- Full design, diagrams, test plan, and decision rationale:
  [2026-06-26-houba-scan-command-group-optional-extra-design.md](../../superpowers/specs/2026-06-26-houba-scan-command-group-optional-extra-design.md).
