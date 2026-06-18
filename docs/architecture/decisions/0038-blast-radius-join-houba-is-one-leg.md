# 38. Closing the incident loop end-to-end does not make houba own runtime presence

Date: 2026-06-18

## Status

Accepted. Re-affirms [32. `attach` is scan provenance, not a vuln store](0032-attach-is-scan-provenance-not-a-store.md)
and the roadmap's "runtime presence / fleet inventory — out of scope" boundary. Full design:
[`docs/superpowers/specs/2026-06-18-blast-radius-join-demo-design.md`](../../superpowers/specs/2026-06-18-blast-radius-join-demo-design.md).

## Context

The reference deployment demonstrates *"which images ship the vulnerable package?"* end-to-end
(Dependency-Track reading houba's CycloneDX referrer, on the reproduced XZ / CVE-2024-3094 incident —
ADR 0035, #136). A stakeholder demo needs the **whole** incident question answered: *where do the
impacted images run, and who do we contact?* Surfacing "where it runs" is the tempting place to
quietly grow houba into a fleet inventory — which would betray the stamper thesis and ADR 0032.

## Decision

The full incident answer is a **3-way join keyed on the image digest**, and houba is **one leg**:

- `CVE → digest` — Dependency-Track (reads the houba SBOM referrer). Shipped.
- `digest → owner` — the houba stamp annotation `io.houba.owners`, read by digest. houba's fact.
- `digest → cluster` — a **separate** runtime source: sandbox pods annotated `houba.io/image-digest`,
  listed via the kube API. **Not houba.**

houba supplies only the two digest-addressable facts (SBOM referrer + owner annotation). It does not
run the query and **does not own runtime presence**. The `digest → cluster` leg is the org's
runtime/observability plane, *demonstrated* by querying the kube API — never modelled as a houba
capability.

- **namespaces-as-clusters** is the sandbox stand-in for the cluster leg (namespaces labelled
  `houba.io/cluster=<name>`). The runtime pods run a node-pullable placeholder image
  (`registry.k8s.io/pause`) annotated with the placed digest — the in-cluster Zot is not
  node-pullable, and the cluster leg is a stand-in regardless; the join (list pods → digest → cluster)
  is real, only the pod's image content is a placeholder. The join key (the digest) and the query are
  identical against real multi-cluster inventory; only the source of `digest → cluster` differs.
- **Zero houba-core.** The join is demo glue — extend `scripts/blast-radius.sh` + a read-only
  ClusterRole (list pods); no new port, adapter, use case, or domain concern. The runtime pods carry
  the placed **digest** as an annotation so the join is exact.
- The bypass image (`bypassed/debian-xz`, never through houba) runs as a workload too, so its
  runtime row carries no SBOM/owner — the coverage blind spot made visible **at runtime**, not only
  in the registry.

## Consequences

- The C4 **Deployment** views (`DeployReference` / `DeployLocal`) gain the marked workload pods and
  **one new** edge — the consumer `→ the kube API` (`digest → namespace`); its existing read of the
  registry stamp (owner) is unchanged. The committed Mermaid exports are refreshed. The abstract
  Context / Container / Component / Hexagon model is **unchanged** — houba core is untouched.
- Entity-ref → person resolution stays **out** (that is the developer coverage portal, roadmap
  *Later*); the demo surfaces `group:default/platform` verbatim.
- The demo is honest that "where does it run" is a namespaces-as-clusters stand-in, with the
  real-inventory upgrade path stated in one line.
- The boundary of ADR 0032 is *re-affirmed by demonstration*: the loop closes end-to-end **without**
  houba crossing into runtime inventory or query.
