# SARIF at the front door — grype demo in the reference deployment — design

Date: 2026-06-19
Status: Approved (brainstorm)

## Goal

Demonstrate, in the reference Argo deployment, that **any analyzer's SARIF lands at the front door,
bound to the image digest, and is read back by digest** — houba's portable-provenance role after the
scanstep was dropped (the regis-governance pivot). Concretely: after `reconcile` places the
front-door images, a one-shot Job runs **grype** (off-the-shelf) on the **SBOM houba already
attached** to each, and `houba attach`es grype's SARIF as a signed referrer on the digest; the
existing **blast-radius** runbook then surfaces the scan summary **by digest**, alongside owner and
cluster.

The demo *is* the proof of houba's two post-pivot principles: **analyzer-agnostic** (grype is an
unmodified off-the-shelf image — swap for trivy and nothing else changes; no derived image, no
bundling) and **houba carries, doesn't gate** (houba only `attach`es; enforcement is out of scope).

Builds on the attach how-to (`docs/how-to/attach-scan.md`) and the blast-radius demo (ADR 0038).

## What already ships

- `houba attach` binds a SARIF report to the digest as a signed OCI referrer (`io.houba.scan.*`
  annotations + the `scan/v1` predicate). The mechanism is complete — no houba-core change here.
- The reference deployment places + stamps + SBOMs the front-door images (`reconcile`), publishes
  SBOMs to Dependency-Track, and runs `blast-radius.sh` joining **owner** (+ **cluster**) on the digest.
- The front-door registry is **Zot**, which supports the OCI 1.1 Referrers API — referrers are
  discoverable by digest at the front door (the Harbor "drops referrers on replication" caveat does
  not apply: the demo reads at the front door, not downstream).

## The gap

The demo never runs a scanner, so nothing exercises the "SARIF at the front door, read by digest"
path; `blast-radius` joins owner + cluster but not the scan verdict.

## Design

### A one-shot scan-attach Job (grype on the SBOM → houba attach)

`deploy/base/job-scan-attach.yaml`, post-`reconcile` (beside `publish-sbom`). One pod, three
sequential steps over a shared `emptyDir` — each tool does only what it is good at, so **grype needs
no registry credentials** (regctl fetches; grype reads a local file):

- **initContainer `houba`** (regctl + python3): for each placed ref (`BLAST_REPOS`, minus
  `bypassed/*`), fetch the CycloneDX SBOM referrer houba already attached —
  `regctl artifact get --subject <ref> --filter-artifact-type application/vnd.cyclonedx+json > /shared/<repo>.sbom.json`.
- **initContainer `anchore/grype`** (unmodified image): `grype sbom:/shared/<repo>.sbom.json -o sarif > /shared/<repo>.sarif`.
  Reads the local SBOM (no registry auth); pulls only its CVE DB.
- **container `houba`**: a `scripts/scan-attach.sh` loop, `houba attach <ref> --report /shared/<repo>.sarif`
  (resolves tag→digest, binds the referrer, signs when `HOUBA_ATTEST_SIGNER` is set).

Covers the placed images (`BLAST_REPOS` minus `bypassed/*`): the debian rebuild (real CVEs) and the
placed XZ fixture (grype's actual output). `bypassed/*` is deliberately skipped so it stays
un-provenanced — the blind spot. `grype sbom:` is the originally-validated invocation, and reusing
the existing SBOM means **no image pull**. The image is **never modified** — `attach` pushes a
*referrer* (subject = the digest); the placed digest (finalized at reconcile-time stamping) stays
stable and is the join key for stamp + SBOM + scan + owner.

### blast-radius gains a SCAN column

`scripts/blast-radius.sh` already joins owner (+ cluster) by digest. Add: for each digest,
`regctl referrers <digest>` filtered to the scan artifactType → read the scan referrer's
`io.houba.scan.*` summary → show a compact `crit/high/med…`, or `— (no scan)` when absent — the same
pattern as the existing stamp read. The **bypass image** (never through the front door → no scan
referrer) shows `— (no scan)` alongside its missing owner/SBOM: the front-door blind spot, now in the
scan dimension too. Everything joins on the digest.

### C4 + runbook + make

- **Deployment views** (`DeployReference` / `DeployLocal`): add the scan-attach Job pod — grype as an
  instance of the existing `upstreamScanner` (ingest mode: scanner → SARIF → houba `attach`),
  co-located with the houba container — plus the CVE-DB egress edge (grype → its DB source). The
  abstract Context / Container / Component / Hexagon views are **unchanged** (houba `attach`es, never
  invokes — `upstreamScanner` ingest-only already models it). Refresh the committed Mermaid exports.
- **Runbook**: a `make scan` step after `reconcile`, then `make blast-radius` shows the SCAN column.
  Narrate honestly — grype's real findings on placed images; the bypass row empty across all
  dimensions.
- No new MirrorPolicy example (the existing reference policy's placed images are scanned).

## Deliberate simplifications (`ponytail:`)

- **Digest-pinned.** scan-attach resolves each tag via `regctl image digest` (the same digest
  blast-radius reads), uses `@digest` for fetch + attach, dedups tags sharing a digest, and falls
  back to the SPDX SBOM when no CycloneDX referrer is present (grype reads either). Run `make scan`
  right after the placing reconcile — referrers are per-digest, so a later reconcile strands them.
- **No enforcement.** The demo stops at "read the verdict by digest"; Kyverno admission (the existing
  `docs/examples/admission/require-fresh-houba-scan.yaml`) is out of scope.
- **CVE-DB egress is real** (grype pulls from its DB source); air-gapped mirroring is a one-line
  runbook note, not implemented.
- **No claim about grype vs the XZ backdoor.** The demo shows grype's actual output; the robust,
  always-true lesson is the bypass image's total absence of provenance.

## Out of scope

- Kyverno admission enforcement (separate concern; the policy example already exists).
- Bundling grype into the houba image (dropped — the demo proves the opposite).
- A second analyzer (trivy) in the demo — grype only; swapping is a one-line change.
- houba-core changes (none — the scan Job is deploy glue; `attach` and `blast-radius.sh` exist).
- **Rebuilt-with-provenance (index) images** — their SBOM/scan referrers do not land on the digest the
  tag resolves to, so variant rows read `-` (e2e-confirmed: the index digest *and* its children carry
  no referrers). A pre-existing houba **referrer-durability gap on the rebuild path** (it also breaks
  `publish-sbom` → Dependency-Track for rebuilds) — tracked as a separate houba-core follow-up. The
  demo's clean rows are the single-manifest path (the `debian-xz` fixture, busybox copies).

## Acceptance

- `make scan` → the scan-attach Job completes; each **single-manifest** front-door image gains a SARIF
  referrer (`regctl artifact list <digest>` shows it, with `io.houba.scan.*`), the image **digest
  unchanged**. (Rebuilt index variants are subject to the referrer-durability gap noted above.)
- `make blast-radius` → the SCAN column shows the `debian-xz` fixture as `C145 H324 M663 L156`,
  busybox copies as `clean`, and the bypass image as `-` (e2e-confirmed on kind).
- `DeployReference` / `DeployLocal` show the scan-attach Job (grype + houba) + the CVE-DB egress;
  Mermaid exports refreshed; abstract views unchanged.
- No change under `houba/` (the scan Job is deploy glue; `attach` and `blast-radius.sh` are existing).
