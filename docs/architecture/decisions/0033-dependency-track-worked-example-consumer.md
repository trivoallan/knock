# 33. Dependency-Track is the reference deployment's worked-example SBOM consumer

Date: 2026-06-16

## Status

Accepted. Refines [32. `attach` is scan provenance, not a vuln store](0032-attach-is-scan-provenance-not-a-store.md).

## Context

ADR 0032 named Dependency-Track as the org's concrete "observability stack" / currency
consumer and *deliberately kept it out of the C4 model* — modeling it as an abstract external
system would betray the portable, tool-agnostic stamp thesis. But the reference deployment is a
**worked example**, and a worked example demonstrates value with concrete, named software
(it already names kind, OpenBao, ESO, Zot). The package-level blast-radius loop — houba's SPDX
SBOM, read downstream to answer "which images ship the vulnerable package?" — was asserted but
not *shown*.

## Decision

The reference deployment runs an off-the-shelf Dependency-Track as the worked-example SBOM
consumer. houba's SBOM (SPDX, buildkit-native) is converted to CycloneDX (DT is CycloneDX-only)
by demo glue and uploaded to DT, closing the loop end-to-end. The boundary of ADR 0032 is
refined, not broken:

- **Deployment views may name DT.** It appears as a deployment node in `DeployReference` and
  `DeployLocal` — worked examples, not the abstract model.
- **The abstract model stays generic.** Context / Container / Landscape keep the unnamed
  "observability / CMDB stack" consumer. DT is never modeled as a system there.
- **DT is glue, not a feature.** No houba `DependencyTrack` adapter/port/use case; houba core
  is untouched and emits SPDX unchanged. Currency/continuous-correlation remains out of
  houba's product scope — the demo wires a third-party tool, houba does not own it.

## Consequences

- A glue image (houba + `syft`) and two Jobs (key bootstrap, SBOM publish) live under
  `deploy/`. They are demo infrastructure; the houba product image never ships `syft`.
- The offline boundary is documented: component inventory works offline; CVE/severity
  correlation needs DT's NVD feeds (online).
- The C4 Deployment views and their committed Mermaid exports gain the DT nodes.
