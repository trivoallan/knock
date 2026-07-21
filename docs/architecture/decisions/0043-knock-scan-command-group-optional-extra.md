# 43. The scan pipeline becomes a `knock scan` command group shipped as an optional extra; SBOM-publish stays a referrer-bridge

Date: 2026-06-26

## Status

Accepted — refines ADR 0042

## Context

ADR 0042 established the scan pipeline as **incremental, reconcile-fed deployment glue** requiring no
knock-core change. #188 then shipped it on Redis Streams, already cleanly split into pure decision
logic (`scripts/scan_queue.py`, unit-tested) and a thin redis-py I/O boundary
(`scripts/scan_streams.py`, integration-tested), with an operator surface (`scripts/scan-dlq.py`).

The question raised: should those scripts — plus SBOM-publish-to-Dependency-Track/GUAC — become a
first-class `knock` command group? The scripts are two populations: substrate-coupled worker
mechanics (run by the ScaledJob) and a human-invoked operator surface (`scan-dlq` triage, run
mid-incident). SBOM-publish is a separate axis that touches knock's "the referrer is the interface"
thesis.

## Decision

- **Scan pipeline → optional extra (Approach D).** Promote #188's split into knock's hexagonal layers
  behind a `QueuePort` + `RedisStreamsAdapter`, shipped as `pip install knock-oci[scan]` — redis-py an
  **optional** dependency. **Core knock stays redis-free.** The pure module moves to
  `knock/domain/scan_queue.py` under the `≥90%` gate + `mypy --strict`. The image runs `knock scan
  worker/reaper/coverage/enqueue`; operators run `knock scan dlq …`. This **refines 0042's "no
  knock-core change"**: the cross-pod fan-out and schedules stay deployment glue, but the *worker
  logic and operator surface* now live in knock as an opt-in extra — a disciplined, documented
  reopening of "zero knock-core" gated behind the optional-dependency boundary and a `QueuePort`
  redis-leak test.
- Sequenced (D′): **Door 0** = redis:8 + redis-py 8 + RESP3 staging (server bump done, #189); **Door
  1** = the internal refactor (two-way door); **Door 2** = the public `knock scan dlq` CLI surface
  (one-way door), only after the boundary proves out.
- **SBOM publish → referrer-bridge (Approach S-C).** The OCI referrer remains knock's SBOM interface.
  The DT push stays a deployment-glue script (`publish-sbom`, rewritten bash→python); GUAC pulls (zero
  knock code); `dt-bootstrap` stays glue. **No `SbomSinkPort`** unless push-delivery becomes a
  permanent product promise.

## Consequences

- knock *contains* the scan orchestration logic (opt-in), reversing the strict "redis confined to the
  image" stance — but only behind `knock-oci[scan]`; a default `uv sync` pulls no redis.
- The #188 decision logic comes under knock's test/type gates, pinning the three silent-failure bugs
  #188 caught. Verified along the way: the confirmed-set `attested_at` is knock's own `clock.now()`
  (cosign surfaces no signed timestamp), threaded via `ScanOutcome` rather than a port extension.
- The `QueuePort` keeps Streams specifics (consumer group, `XAUTOCLAIM`, trim floor) inside the
  adapter, leaving a second broker (SQS/NATS) *possible* without committing to it (one adapter now).
- Full design, diagrams, test plan, and decision rationale:
  [2026-06-26-knock-scan-command-group-optional-extra-design.md](../../superpowers/specs/2026-06-26-knock-scan-command-group-optional-extra-design.md).
