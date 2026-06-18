# Demonstrable blast-radius — owner + cluster join — design

Date: 2026-06-18
Status: Approved (brainstorm)

## Goal

Make the reference-deployment demo answer the **full** incident question end-to-end:
*from a disclosed CVE → which images ship it → where do they run → who do we contact?* Today the
demo answers only the first leg (Dependency-Track, via the merged XZ / CVE-2024-3094 loop). This
adds the **owner** and **cluster** legs, joined on the image **digest**, so a stakeholder watches
the whole chain light up — with houba as **one leg**, never the query engine.

**The boundary — and the guardrail.** houba produces *digest-addressable facts* (a package-SBOM
referrer and an `io.houba.owners` stamp). It does **not** run the query and it does **not** own
runtime presence (where images run). The cluster leg is a *separate* system the consumer joins to
on the digest. The demo must **never** imply houba watches the fleet — re-affirming
[ADR 0032](../../architecture/decisions/0032-attach-is-scan-provenance-not-a-store.md) and the
roadmap's "runtime presence / fleet inventory — out of scope." Any narration that turns houba into
the inventory is a defect.

## What already ships (≈ 80 %)

- **CVE → image** — `#136` (Dependency-Track consumer) + the reproduced XZ / CVE-2024-3094
  incident: houba places → CycloneDX referrer → DT → *"which images ship the vulnerable package?"*
- **SBOM on both paths** — `#140` (copy *and* rebuild), so every placed image is queryable
  (supersedes the XZ spec's "copy does not SBOM").
- **The coverage blind spot** — `bypassed/debian-xz` (never through houba) is `uncovered` in
  `houba audit`.
- **The owner fact** — the XZ policy already declares `owners: [group:default/platform]`
  (`docs/examples/reference/debian-xz/xz.yml`), so the placed image carries `io.houba.owners` —
  one annotation read away.

## The gap

Two legs exist as *facts* but are not *surfaced* in the incident answer:

1. **owner** — stamped, not shown.
2. **cluster** — no running workloads, and no `digest → location` query.

## Design — a 3-way join keyed on the digest

The image **digest** is the spine. Each leg is owned by a different system; the demo *composes*
them, it does not centralise them in houba.

| Leg | Question | Source | Status |
|-----|----------|--------|--------|
| `CVE → digest` | which images ship the package? | Dependency-Track (reads the houba CycloneDX referrer) | **shipped** (#136) |
| `digest → owner` | who do we contact? | the houba stamp annotation `io.houba.owners`, read by digest | **fact shipped**, surfacing new |
| `digest → cluster` | where does it run? | a runtime source — sandbox pods carrying `houba.io/image-digest`, listed via the kube API | **new** |

houba supplies only the middle two **facts**, both addressable by digest. It never owns the
`digest → cluster` leg — that is the org's runtime/observability plane, *demonstrated* by querying
the kube API in the sandbox.

### Artifacts (all under `deploy/` + `scripts/` + `docs/` — zero houba-core)

1. **Run a marked workload per cluster** (the location the join needs).
   The placed image lives in the in-cluster Zot (a ClusterIP); the kind node's containerd cannot
   resolve cluster DNS, so kubelet cannot pull it — a pod referencing it would `ImagePullBackOff`.
   Since the cluster leg is a *stand-in* anyway, the runtime source is **real pods running a
   node-pullable placeholder image** (`registry.k8s.io/pause`), one per namespace standing in for a
   cluster (labelled `houba.io/cluster=<name>`), each **annotated `houba.io/image-digest=<placed
   digest>`** — the digest it represents. A pod annotated with the bypass image's digest makes the
   blind spot visible **at runtime**. A `make incident-deploy` target resolves the placed tag → digest
   via `regctl` (in-cluster) and templates the pods; the digest is the exact one DT flagged.
2. **Extend `scripts/blast-radius.sh`** with the runtime (cluster) leg. The script *already* reads
   `io.houba.owners` per image and rolls up owners (the owner leg is done); it does **not** yet know
   where images run. Add a **`RUNNING IN`** column: for each image's digest, query the in-cluster kube
   API for pods carrying `houba.io/image-digest=<that digest>` → list their namespace /
   `houba.io/cluster` label. This needs a read-only **ClusterRole (list pods)** bound to the consumer's
   ServiceAccount. The bypass row shows its cluster but no stamp/owner — the blind spot, at runtime.
   (The package-level *CVE → image* leg stays in Dependency-Track, shown alongside in the runbook —
   `blast-radius.sh` remains the scanner-agnostic stamp consumer.)
3. **Parity narrative** (doc, folds into the roadmap's adoption docs-polish): job-parity *not*
   mechanism-parity vs the incumbent intake (a CI pipeline + registry-replication fan-out);
   per-team fan-out is a policy `destinations` list, so houba **replaces** registry replication —
   and because replication strips OCI referrers, that is what keeps the SBOM/signature alive in
   every team copy.
4. **Demo runbook** (`docs/examples/reference/debian-xz/DEMO.md`): the ordered walkthrough on the
   real `make` targets + the guardrail.

## C4 impact

- **Deployment views only** (`DeployReference` / `DeployLocal` in `docs/architecture/workspace.dsl`):
  add the marked workload pods (the runtime stand-in) and **one new** read relationship — the
  blast-radius consumer `→ the kube API` (`digest → namespace`). The consumer already reads the
  registry stamp (owner); that edge is unchanged.
- **The abstract model is unchanged.** No new port, adapter, use case, or domain concern — houba
  core is untouched. Context / Container / Component / Hexagon views do not move.
- Refresh the committed Mermaid exports (`docs/architecture/_export/structurizr-DeployReference.mmd`,
  `…-DeployLocal.mmd`) via the cached `structurizr/structurizr` image.
- Mirror this design as a thin ADR (0038) per the house rule.

## Deliberate simplifications (`ponytail:`)

- **namespaces-as-clusters** — two namespaces labelled `houba.io/cluster=…` on the single kind
  cluster stand in for real clusters. Upgrade path: real multi-cluster inventory (kube-state-metrics
  / ArgoCD ApplicationSet / the org's observability) — **same query, same digest key**. The runbook
  states this in one line; the mechanism is identical.
- **marked pods, not real pulls** — the runtime source is pods running `registry.k8s.io/pause`
  annotated with the placed digest, because the in-cluster Zot is not node-pullable (see Artifact 1).
  The join (list pods → digest → cluster) is real; only the pod's *image content* is a placeholder.
  Upgrade path: the org's real runtime inventory reports the genuinely-running digest — same join.
- **owner = a Backstage entity-ref, surfaced verbatim** (`group:default/platform`). Resolving the
  ref to *people* is the developer coverage portal (roadmap *Later*, #142), not this demo.

## Out of scope

- Real multi-cluster infrastructure.
- Entity-ref → person resolution (Backstage portal, *Later*).
- SBOM on copied images (already shipped, #140).
- Any houba-core change (no new port/adapter/use case).
- Re-building the DT / XZ loop (shipped, #136).

## Acceptance

- `make incident-deploy` → a marked pod is `Running` in each `houba.io/cluster`-labelled namespace
  (two for the placed digest, one for the bypass digest), each annotated `houba.io/image-digest`.
- `make blast-radius` → the report gains the `RUNNING IN` column; the placed image shows
  `group:default/platform` (owner, already reported) **and** its two clusters; the bypass row shows
  its cluster but no stamp/owner (the blind spot, at runtime).
- The DEMO.md runbook runs end-to-end in the sandbox in ~12 min on the existing `make` targets, with
  Dependency-Track supplying the *CVE → image* leg.
- No change under `houba/`; `docs/reference/` unchanged (no model touched); the two Deployment
  Mermaid exports refreshed.
