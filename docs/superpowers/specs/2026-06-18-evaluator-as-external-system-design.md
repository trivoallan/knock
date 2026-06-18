# Evaluator as an external system — C4 model + reference-deployment demo — design

Date: 2026-06-18
Status: Approved (brainstorm)

## Goal

Model the scanstep's vulnerability evaluator correctly in the C4 model, and demonstrate it in the
reference deployment. Unbundling the evaluator (it is supplied by the deployment and interchangeable
via `HOUBA_SCAN_EVALUATOR_CMD`) changed its architectural character: it is no longer one of houba's
*bundled* tools (syft / cosign) but a deployment-supplied, interchangeable capability — the
**usage-oracle** pattern (a `subprocess` shell-out, owned outside houba, modelled as an external
system). The model must reflect that, and the reference deployment must exercise it.

Builds on the scanstep ([spec](2026-06-18-scanstep-vuln-gate-design.md),
[ADR 0039](../../architecture/decisions/0039-scanstep-runs-the-scanner-gates-at-admission.md)).

## What already ships

- The scanstep (PR #163): `VulnEvaluatorPort` + `CommandScanAdapter` + reconcile stage→scan→promote.
- The C4 already models `adScan` (CommandScanAdapter, `subprocess`) at the Component / Hexagon level.
- The reference deployment runs houba as a CronJob on the base image; the scanstep is **inert** there
  (no `HOUBA_SCAN_EVALUATOR_CMD`, no `enforceFrom` / `auditFrom`).

## The gap

- The C4 context/landscape carries `upstreamScanner` — *"houba ingests the report; it never calls the
  scanner."* False as a general principle now that the scanstep **invokes** an evaluator.
- The reference deployment neither configures nor demonstrates the scanstep; the Deployment views
  don't show the evaluator.

## Design

### Section 1 — Abstract model: one external system, two relations *(lands in PR #163)*

Reshape `upstreamScanner` → `vulnScanner` (`softwareSystem`, `"External"`):
> "Emits SARIF vulnerability reports. houba INGESTS a report produced in CI / a scan service (attach),
> and INVOKES a configured one on the SBOM at admission (scanstep gate). houba owns neither the tool
> nor its CVE database."

Two relationships — the two integration modes:
- `vulnScanner -> houba "Produces scan reports, ingested by attach" "SARIF / file"`
- `houba -> vulnScanner "Invokes on the SBOM at admission (scanstep gate)" "subprocess (HOUBA_SCAN_EVALUATOR_CMD)"`

Container / Component: keep `portVulnEvaluator` + `adScan` (`subprocess`); add `adScan -> vulnScanner`
("drives the configured evaluator"), mirroring `adUsageOracle -> usageOracle`. The
"never calls the scanner" wording is dropped — houba *invokes* but does not *own* (neither the tool
nor its CVE DB). One box, two opposite-direction arrows — the only bidirectional pair in the model,
legitimate because attach (scanner→houba) and the scanstep (houba→scanner) are genuinely distinct
modes of the same tool class. Refresh the Context / Landscape / Container Mermaid exports.

### Section 2 — Identity narrative: minimal *(lands in PR #163)*

`design.md` carries **no** "never runs a scanner" claim to correct (its "never runs the *query*" is the
blast-radius, unrelated and still true). ADR 0032's thesis — *not a vuln store; currency delegated to
Dependency-Track* — holds: the scanstep is a point-in-time admission gate, not a store. The only
change is a bidirectional cross-link in ADR 0032 → ADR 0039:
> Related: ADR 0039 extends this boundary — the scanstep *invokes* an evaluator at admission (a
> point-in-time gate), still not a store and still delegating currency to Dependency-Track.

Adding an identity sentence to `design.md` would be scope creep — nothing there is false.

### Section 3 — Deployment views + runnable demo *(own follow-up PR)*

The Deployment views must be backed by a real demo (anti-drift). **The XZ fixture cannot be reused:**
blast-radius needs it *placed*, and grype-via-SBOM does **not** flag CVE-2024-3094 (the backdoor
evades package-version scanning — precisely the XZ demo's point, "houba does not detect the
backdoor"). So the scanstep demo is a **complementary** narrative, not a merge.

- **New gated fixture** — a small policy importing a known-CVE image (one grype flags via SBOM, e.g.
  an EOL base), `enforceFrom: critical` (+ `auditFrom: high`) → reconcile **blocks** it (never placed);
  a `make` target shows the block in the reconcile report. XZ stays untouched.
- **Derived image** — `FROM houba … COPY --from=anchore/grype …`, referenced by the reconcile
  workload, with `HOUBA_SCAN_EVALUATOR_CMD=grype sbom:{sbom} -o sarif`. The concrete deployment impact
  of unbundling.
- **CVE-DB egress** — grype pulls its DB from `grype.anchore.io` on first run → a new **egress edge**
  in the Deployment view + an "air-gapped ⇒ mirror the DB" note.
- **C4 Deployment** — `vulnScanner` as a `softwareSystemInstance` **co-located in the houba pod**
  (carried by the derived image — a logically-external system physically embedded, a standard C4 case)
  + the egress edge. Refresh `DeployReference` / `DeployLocal`.

The two demos together tell the whole story: **the scanstep blocks known CVEs at the door;
blast-radius traces what evades the scan.**

## Deliberate simplifications (`ponytail:`)

- The demo gates **one** fixture; not a matrix of severities / destinations.
- grype is the reference evaluator in the demo; the design stays tool-agnostic (any SARIF emitter).
- CVE-DB egress is real (kind pulls it); air-gapped mirroring is *documented*, not implemented.

## Out of scope

- Merging the scanstep into the XZ / blast-radius flow (kept complementary).
- Air-gapped CVE-DB mirroring infrastructure.
- A second evaluator (trivy / regis) in the demo — grype only; swapping is config.

## Acceptance

- **Sections 1 + 2 (PR #163):** `vulnScanner` external system with both relations; the
  "never calls the scanner" wording gone; the `adScan -> vulnScanner` edge present; the ADR 0032 ↔ 0039
  cross-link; Context / Landscape / Container Mermaid refreshed; `make reference` unchanged (no model
  field changes).
- **Section 3 (follow-up):** a `make` demo **blocks** the gated fixture (not placed, shown in the
  report) while XZ / blast-radius still works; the reconcile workload runs the derived image with
  `HOUBA_SCAN_EVALUATOR_CMD`; `DeployReference` / `DeployLocal` show the co-located `vulnScanner`
  instance + the CVE-DB egress; exports refreshed.
