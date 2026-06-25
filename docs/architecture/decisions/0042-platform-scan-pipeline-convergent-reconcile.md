# 42. The platform-internal scan/SBOM pipeline is a convergent K8s reconcile — not Kargo, not a workflow engine

Date: 2026-06-25

## Status

Accepted

## Context

The platform/security team needs to run its own post-placement loop over the production Harbor
(~150k images, >300 clusters): `regis scan` → `houba attach` the signed verdict → publish the SBOM
to Dependency-Track. Two off-the-shelf framings were proposed and rejected. **Kargo** is a
stage-to-stage *promotion* engine, not a per-artifact post-processor: Freight is not a 150k work
queue, there is no rescan-cadence primitive, and it would use ~10 % of the tool. A **workflow
engine** (Argo Workflows) is net-new infrastructure at this scale, and the work has almost no DAG —
the SBOM is produced by syft at placement (independent of the scan), and `scan && attach` is two
lines of shell.

## Decision

- The pipeline is **two independent convergent reconcile loops on bare K8s** — `scan-coverage` and
  `dt-publish` — each a CronJob (`concurrencyPolicy: Forbid`) fanning a `houba audit` gap into a
  `parallelism`-capped indexed Job. Ordering/retry/artifact-passing come from **convergence +
  idempotency + the digest-bound referrer substrate**, not a DAG runtime. `dt-publish` generalises
  the existing demo `publish-sbom` Job.
- **Kargo is reserved for the project-team promotion gate** (ADR 0041 / the Kargo-gate spec),
  deferred — not this loop.
- **Argo Workflows is a deferred upgrade**, adopted only when the fan-out glue would otherwise grow
  its own persistent state (memory / retry queue / status API).
- The **one houba-core change** is a `houba audit --scan` presence tier (twin of `--signed` / the
  `--sbom` tier of [ADR 0036](0036-audit-digest-and-sbom-tier.md)), listing the scan-result referrer
  `application/vnd.houba.scan.result.v1` — which `audit` does not check today. **Freshness stays out
  of `audit`**, honouring the scan-max-age spec (freshness is producer-side `attested_at`, enforced
  at the gate `houba verify` / admission / Kargo); the scheduler layers staleness from the cheap
  unsigned scan-timestamp annotation, a non-adversarial scheduling decision.

## Consequences

- houba stays scanner-free and gate-free: `audit` reports presence, the loop schedules, `verify` /
  Kargo gate. No new port/adapter; the change is one observational audit tier.
- The gating risk is the **walk**, not the orchestrator: `audit` is "Sequential v1" — its time over
  a real Harbor slice must be measured before relying on it at 150k (shard/parallelise if needed).
- `workspace.dsl` is deferred to implementation (deferral recorded in the spec): the only delta is
  two deployment-level CronJobs; DT, regis, and the existing CronJobs are already modelled.

Full design: [the spec](../../superpowers/specs/2026-06-25-platform-scan-pipeline-orchestration-design.md)
