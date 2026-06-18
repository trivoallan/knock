# 39. The scanstep runs the scanner at admission and gates per destination — without becoming a vuln store

Date: 2026-06-18

## Status

Accepted. Extends ADR 0021 (`attach --fail-on`, the first enforcement lever) into the reconcile
path, and re-affirms
[32. `attach` is scan provenance, not a vuln store](0032-attach-is-scan-provenance-not-a-store.md).
Full design:
[`docs/superpowers/specs/2026-06-18-scanstep-vuln-gate-design.md`](../../superpowers/specs/2026-06-18-scanstep-vuln-gate-design.md).

## Context

`attach --fail-on` lets a CI pipeline gate on a scan report the caller supplies. In the
reconcile / operator world there is no surrounding CI to run the scanner — houba *is* the
automation — so vulnerable images can be admitted through the front door ungated. Adding a scanner
to `reconcile` is the tempting place to quietly grow houba into a continuous vuln tracker, which
would betray the stamper thesis and ADR 0032.

## Decision

`reconcile` runs a vulnerability evaluator on the SBOM it already generates and gates publication
per destination, as a **point-in-time admission gate**:

- **One port, one shell-out adapter.** `VulnEvaluatorPort` (SBOM → SARIF); a command adapter driven
  by `HOUBA_SCAN_EVALUATOR_CMD` (mirrors `CommandUsageAdapter`). houba owns no CVE database and no
  scanner internals; grype / trivy / regis are interchangeable commands that emit SARIF. The whole
  downstream — SARIF mapper, severity bucketing, `gate_breached`, the `scan/v1` predicate,
  referrer + annotations — is reused unchanged.
- **The scanner is config, the gate is policy.** `HOUBA_SCAN_EVALUATOR_CMD` is the capability;
  `Destination.enforceFrom` / `auditFrom` (Severity cut points) are the governance. A threshold
  with no evaluator configured is a `ConfigError`.
- **Evaluate once per variant, act per destination; gate before publish.** Enforce blocks *before*
  the image is made consumable (copy: scan the source; rebuild: build local → scan → push if clean),
  so a blocked image is never published — nothing to roll back, zero exposure window, no delete.
- **The boundary holds.** A re-scan of an already-placed image is **Audit-only**, never a delete
  (the no-delete ethos + the 7-day digest-stability window). *"Is it vulnerable today?"* stays
  Dependency-Track's question.

## Consequences

- The C4 **Component + Hexagon** views gain `VulnEvaluatorPort` + the evaluator adapter (and the
  relationships); the committed Mermaid exports are refreshed. Context / Container / Landscape are
  unchanged.
- The runtime image stays **evaluator-agnostic** — the scanner is *not* bundled (that would privilege
  one tool and contradict the interchangeable `HOUBA_SCAN_EVALUATOR_CMD` contract, and would not solve
  CVE-DB freshness anyway). The chosen SARIF tool is supplied by the deployment via a derived image
  (`FROM houba … COPY the evaluator`); houba bundles only what it *always* runs (regctl / buildctl /
  cosign / syft). See `docs/examples/scan-gate/`.
- The MirrorPolicy schema gains two `Destination` fields → `make reference` regenerates the
  policy + config reference.
- The reconcile flow reorders from `place → SBOM` to **stage → scan → promote** on the gated paths
  (build/copy to a `.houba-staging` tag, scan, promote to the consumable tag only if it passes) —
  uniform across copy and rebuild, no build-adapter change.
- `db_version` is propagate-or-omit (the ADR 0020 ethos): stamped only when the evaluator surfaces it.
- Enforcement coverage extends from CI (`attach --fail-on`) to the operator / reconcile front door,
  while ADR 0032's "not a vuln store" boundary is re-affirmed by construction.
