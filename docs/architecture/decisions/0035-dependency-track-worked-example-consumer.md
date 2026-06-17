# 35. Dependency-Track is the reference deployment's worked-example SBOM consumer

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
consumer. houba attaches a CycloneDX SBOM referrer to every placed image (`HOUBA_SBOM_FORMATS`
includes `cyclonedx-json`, per ADR 0034); demo glue (`publish-sbom`) fetches that referrer and
uploads it to DT, closing the loop end-to-end. The boundary of ADR 0032 is refined, not broken:

- **Deployment views may name DT.** It appears as a deployment node in `DeployReference` and
  `DeployLocal` — worked examples, not the abstract model.
- **The abstract model stays generic.** Context / Container / Landscape keep the unnamed
  "observability / CMDB stack" consumer. DT is never modeled as a system there.
- **DT is glue, not a feature.** No houba `DependencyTrack` adapter/port/use case; houba core
  is untouched (it just emits a CycloneDX referrer alongside SPDX — a config flag, ADR 0034).
  Currency/continuous-correlation remains out of houba's product scope — the demo wires a
  third-party tool, houba does not own it.

## Consequences

- The demo glue is two one-shot Jobs (API-key bootstrap, SBOM publish) plus the incident seed,
  all under `deploy/`. No custom image: `publish-sbom` runs the stock houba image (regctl +
  python) and fetches the native CycloneDX referrer — no SPDX→CycloneDX conversion, no syft.
- The offline boundary is documented: component inventory works offline; CVE/severity
  correlation needs DT's NVD feeds (online).
- The C4 Deployment views and their committed Mermaid exports gain the DT nodes.
