# Scan gate — block vulnerable images at admission

> Design: [scanstep spec](../../superpowers/specs/2026-06-18-scanstep-vuln-gate-design.md) ·
> [ADR 0039](../../architecture/decisions/0039-scanstep-runs-the-scanner-gates-at-admission.md).

`reconcile` runs a vulnerability evaluator on the SBOM it generates and **gates publication per
destination**, *before* the image is made consumable. The scanner is a deployment capability
(`HOUBA_SCAN_EVALUATOR_CMD`, e.g. `grype sbom:{sbom} -o sarif` — any SARIF-producing tool); the
**gate** lives in the policy as two per-destination cut points on each `Destination`:

- `enforceFrom` — **block** publish to this destination if any finding is at or above this severity.
- `auditFrom` — **publish, but flag a warning**, at or above this severity.

When both are set, `enforceFrom` must be at least as strict as `auditFrom`. The canonical posture is
one line: `enforceFrom: critical` + `auditFrom: high` = *block criticals, warn highs, ignore the
rest.*

This is a point-in-time **admission** gate, not continuous vulnerability tracking — *"is it
vulnerable today?"* stays Dependency-Track's question
([ADR 0032](../../architecture/decisions/0032-attach-is-scan-provenance-not-a-store.md)). A re-scan
of an already-placed image is audit-only, never a delete.

See [`scan-gate.yml`](scan-gate.yml): redis is published to `prod` only if it has no **critical**
findings (highs are published with a warning), while `staging` observes (warns on criticals) but is
never blocked.

## Supplying the evaluator

houba's image does **not** bundle a scanner — the evaluator is interchangeable, so you choose it.
Point `HOUBA_SCAN_EVALUATOR_CMD` at any tool that emits SARIF and add it to a derived image:

```dockerfile
FROM houba:<version>
# grype (Anchore) — or swap for trivy / regis, any SARIF emitter
COPY --from=anchore/grype:v0.114.0 /grype /usr/bin/grype
```

```bash
HOUBA_SCAN_EVALUATOR_CMD='grype sbom:{sbom} -o sarif'   # trivy: 'trivy sbom {sbom} -f sarif'
```

houba writes the SBOM to a temp file and substitutes its path for `{sbom}`; the tool's SARIF on
stdout feeds the gate. Keeping the scanner — and its CVE database — outside houba's release is
deliberate ([ADR 0039](../../architecture/decisions/0039-scanstep-runs-the-scanner-gates-at-admission.md)):
bundling one tool would privilege it and would not solve database freshness.
