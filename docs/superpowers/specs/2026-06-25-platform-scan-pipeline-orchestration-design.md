# Platform-internal scan + SBOM pipeline — convergent reconcile, not Kargo, not a workflow engine

> **Status:** Design (approved) — pre-implementation. Decided in an office-hours design pass
> (2026-06-25). One small houba-core change is implied (§4); everything else is deployment glue
> outside the hexagon. Builds on `houba audit` ([audit.py](../../../houba/use_cases/audit.py), the
> `--signed`/`--sbom` tiers), the scan-result referrer (`houba attach`), the demo's `publish-sbom`
> Job, and the producer-side freshness decision in
> [2026-06-16-scan-max-age-design.md](2026-06-16-scan-max-age-design.md).

## 1. Context & motivation

The platform/security team owns the software supply chain of a large group: **>300 Kubernetes
clusters, a Harbor with ~150k images**. houba is already the front door (rebuild/harden, stamp,
SBOM); `regis` already governs (scan / policy → SARIF verdict). What is missing is the **operational
loop that runs the platform team's own post-placement work** over the live registry:

1. **scan** each placed image with regis,
2. **attach** the signed verdict to the digest (`houba attach`),
3. **publish** the package SBOM to Dependency-Track (the currency / blast-radius layer).

Scope of this spec is **platform-internal only** — nothing touching the end consumers (project
teams) yet. It answers one question: *what orchestrates that loop at 150k scale?*

## 2. What this is NOT (two rejected framings)

**Not Kargo.** [Kargo](https://kargo.io/) is a stage-to-stage **promotion** engine; this work is
**event/convergent per-artifact post-processing**. Kargo's *Freight* is not a 150k work queue,
Kargo has no rescan-cadence primitive, and bending it here uses ~10 % of the tool while ignoring the
promotion/Git model that *is* Kargo. Kargo stays reserved for the **project-team promotion gate**
(the read-side gate validated on kind in
[2026-06-23-kargo-promotion-gate-design.md](2026-06-23-kargo-promotion-gate-design.md) §9), which is
deliberately deferred. Using Kargo for the platform-internal loop is adopting a promotion engine in
order *not* to promote.

**Not a workflow engine (Argo Workflows) on day 1.** It is **net-new platform infrastructure** at
300-cluster scale (a controller + Server UI + RBAC + artifact repo to operate and secure), and the
work has **almost no DAG** (§3). A DAG engine earns its place with inter-step dependencies, per-step
retry, and artifact passing — the case this work has the *least*. It is the deferred **upgrade**
(§6), not the starting point.

## 3. The shape — two independent convergent reconcile loops

### 3.1 Why convergent

A webhook-driven design is **lossy** (a missed Harbor push event = an image silently never scanned)
and does **not** cover the dominant workload, which is not "a new image" but "**a CVE dropped,
rescan a cohort of already-placed images**". A reconcile sweep is **self-healing** (a missed event
is caught on the next pass) and **absorbs the rescan cadence in the same mechanism**. It also
mirrors houba's own philosophy — everything houba does is a convergent reconcile. The Harbor webhook
becomes a *latency optimisation* to bolt on later, never the backbone.

### 3.2 There is no chain — there are two independent gaps

The SBOM is **not** produced by the scan. houba generates it with syft **at placement** and attaches
it as an OCI referrer. So "publish SBOM to DT" does not depend on the scan at all:

- **Loop A — scan-coverage:** `audit` says *"digest X has no scan verdict"* → `regis scan` then
  `houba attach`.
- **Loop B — dt-publish:** `audit` says *"digest X has an SBOM referrer not yet in DT"* → upload it.
  This is the **existing demo `publish-sbom` Job** (`make publish-sbom`: fetch the CycloneDX referrer
  houba attaches, upload via DT's BOM API) generalised from a one-shot into a convergent CronJob.

No inter-loop ordering to orchestrate; the only sequence that remains, `regis scan && houba attach`,
is two lines of shell in one container, not a DAG.

### 3.3 What replaces the workflow engine's three services

| Engine service | Bare-K8s replacement |
|---|---|
| **Ordering** | none needed between loops (independent); within a loop it is shell order |
| **Retry** | **convergence + idempotency**: a partial failure reappears in the next `audit` gap; a step already done is never re-scheduled (the gap is defined as "missing"). Native `backoffLimit` / `backoffLimitPerIndex` cover transient retry |
| **Artifact passing** | none: each step's artifact is a **digest-bound referrer** (verdict, SBOM); the next step reads the registry, not a passed file. The referrer substrate *is* the bus |

### 3.4 Primitives

- A **tooling image** = `regis` + the `houba` CLI + a small **python** DT pusher (the houba runtime
  image ships no curl/jq by design — see [[houba-image-no-curl]]; DT's BOM upload is a POST to
  `/api/v1/bom`, idempotent, DT replaces per project).
- Two **CronJobs** (`concurrencyPolicy: Forbid` so sweeps never overlap) — `scan-coverage` and
  `dt-publish` — each fans a `houba audit` gap into a **`parallelism`-capped indexed Job** (one
  index per digest).
- **Dashboards** = the audit gap number itself (the KPI: gap → 0 = success, a stuck non-zero gap =
  alert), DT for the vuln/SBOM view, pod logs for "why did this scan fail".

## 4. The one houba-core change — `audit` gains a scan-verdict *presence* tier

`houba audit` today carries `digest` + `--signed` + `--sbom` tiers (signed-coverage-audit spec;
`--sbom` = ADR 0036), but is **blind to the scan verdict**: `--signed` lists *any* cosign bundle
(`application/vnd.dev.sigstore.bundle.v0.3+json`) and so cannot tell a provenance signature from a
scan attestation; nothing lists the scan-result referrer
([`application/vnd.houba.scan.result.v1`](../../../houba/domain/scan/constants.py)). So Loop A's
worklist — "which digests lack a scan verdict" — is not computable from `audit` today.

**Change:** add a `--scan` tier, the exact twin of `--signed` / `--sbom`:

- `audit_coverage(..., check_scan: bool = False)`, `CoverageOutcome.scan: bool | None`, counts
  `with_scan` / `without_scan` (NOT `scanned` — that name is already the total-walked count), probed
  on covered images only, via `list_referrers(ref, SCAN_RESULT_ARTIFACT_TYPE)`. Observational, one
  cheap referrer listing — same ceiling as the other two tiers.

**Freshness stays OUT of `audit` — deliberate, not an omission.** The
[scan-max-age spec](2026-06-16-scan-max-age-design.md) already resolved (fork 1) that **houba does
not gain an audit-side freshness tier**: an audit tier reports drift but cannot block, so freshness
is **producer-side** (the signed `ScanPredicate.attested_at`) and enforced at the **gate**
(`houba verify` — [verify.py](../../../houba/use_cases/verify.py) `max_age` —, admission, Kargo).
This spec honours that. The **scheduler** layers staleness itself, cheaply and outside houba-core,
from the unsigned `{prefix}.scan.timestamp` annotation on the scan-result referrer
([summary.py](../../../houba/domain/scan/summary.py)) — adequate because scheduling a rescan is a
**non-adversarial** decision; the signed `attested_at` is required only at the adversarial gate. This
keeps **houba ≠ scanner ≠ gate** intact: `audit` reports presence, the loop schedules, `verify` /
Kargo gate.

**Fork (recorded):** the scheduler could instead walk referrers itself, leaving `audit` untouched.
Rejected in favour of the `audit` tier — it is consistent with the existing tiers, reuses the same
detection, and the coverage portal (ADR 0035/0036) gets a scan column for free. The diff is the
`--sbom` twin.

## 5. The real risk is the walk, not the orchestrator

`audit.py` describes itself as **"Sequential v1"**. A sequential catalog walk over 150k images **per
sweep** is the gating concern. **Before any YAML is written**, run the existing
`houba audit --check-signed --check-sbom` against a real Harbor slice (e.g. 5k images) to measure the
slope toward 150k. If it does not hold, shard the walk by registry/repo or parallelise it — a
separate, scoped change. This is the first real-world step; the orchestration is downstream of it.

## 6. Upgrade trigger to Argo Workflows (stated testably)

The fan-out glue (read gap → apply N Jobs) is the one thing a workflow engine would hand you. Keep it
**stateless** — read the gap, apply Jobs, exit; K8s holds the state. The moment the glue wants its
**own memory / retry queue / status API**, you are reinventing Argo Workflows badly: stop and adopt
it then. Until that line is crossed, bare K8s + DT + `audit` is less to run and operate.

## 7. Scope

**In scope (once §5 holds):** the `--scan` audit tier; the two convergent CronJobs + indexed Jobs;
the tooling image; the `dt-publish` loop generalised from the demo `publish-sbom` Job.

**Out of scope:** Kargo for this loop (it is the project-team promotion gate, deferred); a workflow
engine on day 1 (deferred upgrade, §6); an audit **freshness** tier (rejected by the scan-max-age
spec — freshness is producer-side + gate-enforced); any end-consumer / project-team surface; a Harbor
webhook (latency optimisation, later).

## 8. C4 / ADR / examples sync

Mirrored as **ADR 0042** (thin, links here). The **examples** obligation does not fire: no
`MirrorPolicy` / user-facing policy change — the deliverables are deployment manifests and one CLI
flag.

**workspace.dsl deferred to implementation, deferral recorded** (Kargo-spec precedent). The
structural delta is at **deployment** level only — Dependency-Track, regis, the `publish-sbom` Job,
and the `houba-reconcile` / `houba-gc` CronJobs are **already modelled**; the only addition is the
two new reconcile CronJobs (`scan-coverage`, `dt-publish`) against the production Harbor. No
context-level actor or external system is added (DT and regis already exist in the model). Modelling
it before the §5 walk-feasibility check would be speculative; the C4 edit fires when implementation
is green-lit.
