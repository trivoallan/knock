# Scanstep — run the scanner at admission, gate per destination — design

Date: 2026-06-18
Status: Approved (brainstorm)

## Goal

Make `reconcile` itself answer *"is this image clean enough to admit?"* at the front door,
instead of relying on a separate CI step. Today houba only **ingests** an externally-produced scan
report (`houba attach`, with `attach --fail-on` as a CI gate). In the reconcile / operator world
there is no surrounding CI to run the scanner — houba *is* the automation. The scanstep closes that
gap: `reconcile` runs a vulnerability evaluator on the **SBOM it already generates**, gates
publication per destination, and attaches the result.

**The boundary — and the guardrail.** The scanstep is a **point-in-time admission gate**, exactly
like `attach --fail-on`. It is **not** continuous vulnerability correlation: *"is it vulnerable
today?"* stays Dependency-Track's question
([ADR 0032](../../architecture/decisions/0032-attach-is-scan-provenance-not-a-store.md)). A re-scan
of an *already-placed* image that newly fails can only be **Audit** (reported), never a delete —
re-affirming the no-delete ethos and the 7-day digest-stability window. Any behavior that turns
houba into a fleet vuln tracker is a defect.

## What already ships (≈ 80 %)

The entire downstream is built — the scanstep is **wiring, not greenfield**:

| Brick | Where |
|-------|-------|
| SARIF reader + CVSS→severity bucketing | `houba/domain/scan/formats/sarif.py` (`SarifMapper`); the registry says literally `# v1: SARIF only` |
| Severity enum `critical > high > medium > low > unknown` | `houba/domain/scan/summary.py` (`Severity`) |
| The gate `gate_breached(facts, threshold)` | `summary.py` — reused **verbatim** per destination |
| Signed predicate `houba.dev/predicate/scan/v1` (carries `attested_at`) | `houba/domain/scan/attestation.py` |
| Annotations + `put_referrer` + `attestor.attest` | the SBOM block in `reconcile._do_import` (lines ~457–499) |

houba's "SARIF-only" decision is *already* the implemented reality of `attach`. The scanstep reuses
all of it; only the front — *running* the scanner — is new.

## The gap

`reconcile` places an image and generates its SBOM, but never evaluates it for vulnerabilities or
gates on the result. Only the manual `attach` path can scan-and-gate, and it requires the caller to
bring a report.

## Design

### One new port, one shell-out adapter

- **`VulnEvaluatorPort`** (`houba/ports/`): `evaluate(sbom: SbomDocument) -> ScanResult`, where
  `ScanResult(sarif: bytes, db_version: str | None)`. Pure protocol; houba owns no CVE database.
- **A command adapter** driven by **`HOUBA_SCAN_EVALUATOR_CMD`** (mirrors `CommandUsageAdapter` /
  `HOUBA_USAGE_ORACLE_CMD`): shells a configured command that consumes an SBOM and emits **SARIF**
  on stdout. Scanner-agnostic — grype, trivy, regis-once-it-emits-SARIF are all just commands. The
  validated reference command is `grype sbom:<sbom> -o sarif`. Lazy binary resolution (the
  buildkit/syft pattern). Raises `ScanEvaluatorError` (`AdapterError` → exit 2).
- `db_version` is **propagate-or-omit** (the `.revision` ethos, ADR 0020): stamped only if the
  evaluator surfaces it. SARIF carries no standard DB-version field, so absent ⇒ omitted, never
  fabricated.

### Policy vs config — the scanner is config, the gate is policy

- **Config** (`HOUBA_SCAN_EVALUATOR_CMD`): *which* SARIF-producing command — a deployment
  capability, like `HOUBA_SBOM_FORMATS` and the bundled syft/cosign binaries. Keeps houba
  scanner-agnostic.
- **Policy** (`MirrorPolicy`): *the governance decision* — two per-destination cut points on the
  `Destination` model:
  - `enforceFrom: Severity | None` — **block publish** to this destination if any finding is ≥ this rank.
  - `auditFrom: Severity | None` — **publish, but emit a warning** event, if any finding is ≥ this rank.
  - Validation: when both are set, `enforceFrom` rank ≥ `auditFrom` rank. A destination declaring
    either threshold while **no** `HOUBA_SCAN_EVALUATOR_CMD` is configured ⇒ `ConfigError` (you
    asked for a gate and gave houba no scanner).

This mirrors the existing split exactly: `attach` attaches by default, `--fail-on` adds the gate;
here a destination is scanned **because** it declares a threshold, and the threshold *is* the gate.
Canonical posture in one line: `enforceFrom: critical` + `auditFrom: high` = block criticals, warn
highs, ignore the rest.

### Evaluate once, act per destination; gate *before* publish

The scan is a property of the **image content** (the SBOM) → run **once per variant** (memoize by
SBOM / image digest across a variant's destination fan-out). The *action* is per destination.

Per the resolved decision, **Enforce gates before publication** — the SBOM + scan run on the image
*before* it is made consumable, so a blocked image is simply never published (nothing to roll back,
zero exposure window). This **reorders** the current `place → SBOM` flow into **stage → scan →
promote**, uniformly for copy *and* rebuild (no change to the build adapter):

1. build / copy to a **staging tag** (a `.houba-staging` suffix, filtered from selection and cleaned
   up at the end of the op, pass or fail);
2. generate the SBOM and scan it on the **staging** digest — the existing `syft registry:<ref>`
   mechanism, unchanged (only the ref differs);
3. per destination, apply the gate against the scan `facts`;
4. on pass → **promote** (a registry-side copy from the staging tag to the consumable `out_tag`) +
   attach the SBOM/SARIF referrers + sign; on an Enforce breach → do **not** promote, emit a blocked
   event; the staging tag is removed either way.

The consumable `out_tag` is never advanced to a blocked image — zero exposure on the published name.
The placed digest is identical whether read from staging or the promoted tag (content-addressed), so
the referrers computed on staging attach unchanged to the promoted digest — **one generation** feeds
the gate and the referrers.

Per destination, against the scan `facts`:

- `gate_breached(facts, enforceFrom)` → **skip publish** to that destination; emit a blocked
  (`failed`) `OperationEvent`.
- else `gate_breached(facts, auditFrom)` → **publish + warn** (`OperationEvent` carrying the breach).
- else → publish clean.

In every published case the SARIF is attached as an OCI referrer and the `scan/v1` predicate signed
(when `HOUBA_ATTEST_SIGNER` is set) — exactly the existing SBOM / attach machinery.

### What gets stamped

Reuse `build_scan_annotations` + `build_scan_statement` unchanged: scanner name/version come from
the SARIF (`tool.driver`), plus `format`, the `summary` facts, `report_digest`, `attested_at`.
Extend only with `db_version` when present (propagate-or-omit).

## C4 impact

- **Component + Hexagon views** (`docs/architecture/workspace.dsl`): add `VulnEvaluatorPort` (Port)
  and the evaluator adapter (Adapter, technology = the scanner CLI), with relationships
  use-case → port, adapter → port, adapter → the scanner CLI. Refresh the committed
  `structurizr-Component.mmd` + `structurizr-Hexagon.mmd` exports. Context / Container / Landscape
  are unchanged.
- **Runtime image**: the Dockerfile bundles the reference scanner (grype) alongside
  regctl / buildctl / cosign / syft.
- **Reference**: `make reference` regenerates `mirror-policy.{md,schema.json}` (the new `Destination`
  fields) and `config.md` (the new `HOUBA_SCAN_EVALUATOR_CMD`).
- Mirrored as thin **ADR 0039**.

## Deliberate simplifications (`ponytail:`)

- **Scan once per variant, not once per digest globally** — memoize within a variant's destination
  fan-out. Upgrade path: a run-level cache keyed on image digest if identical content recurs across
  imports.
- **`db_version` best-effort** — only what the evaluator surfaces; SARIF lacks a standard field, so
  absent ⇒ omitted. Upgrade path: an evaluator-specific enrichment (e.g. `grype db status`) if the
  freshness fact becomes load-bearing.
- **No observational-only mode in policy** — to attach a SARIF without any gate, set `auditFrom` at
  the level you care about, or run `houba attach` manually. A dedicated `scan: audit` mode is YAGNI
  until asked.

## Out of scope

- Continuous vulnerability currency / re-scan-as-correlation — Dependency-Track's job (ADR 0032). A
  re-scan of an already-placed image is **Audit-only**, never a delete.
- Non-SARIF evaluator output — the contract is SARIF (the `SarifMapper`); other tools conform by
  emitting SARIF (regis gains a `-o sarif`).
- Managing the evaluator's CVE database (freshness / air-gapped mirroring) — the deployment's job,
  behind `HOUBA_SCAN_EVALUATOR_CMD`.
- Emitting `Audit` results as Kyverno **PolicyReport** CRDs — *Later* (the existing `admission/`
  Kyverno example gates on freshness; PolicyReport-shaped audit output would let the same
  `kubectl get policyreport` surface scan failures).

## Acceptance

- **Domain** (≥ 90 % cov): per-destination resolution of `enforceFrom` / `auditFrom`; validation
  `enforceFrom` ≥ `auditFrom`; a destination with a threshold and no evaluator → `ConfigError`.
  (`gate_breached` + the SARIF bucketing are already covered.)
- **Integration**: a `grype` (scanner) fake-bin under `tests/fake-bins/` emitting canned SARIF; the
  command adapter parses it and raises `ScanEvaluatorError` on non-zero exit / garbage output.
- **Use case**: `reconcile` against a vulnerable SBOM → Enforce destination **not published**, op
  `failed`; Audit destination **published + warning event**; against a clean SBOM → published
  everywhere, SARIF referrer attached, `scan/v1` predicate signed when a signer is set.
- **Docs / model**: `docs/examples/scan-gate/` present; `make reference` clean (regenerated);
  `workspace.dsl` + Component/Hexagon exports updated; ADR 0039 committed.
