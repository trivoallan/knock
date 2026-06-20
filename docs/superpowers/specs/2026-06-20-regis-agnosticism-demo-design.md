# Two analyzers at the front door — regis + grype agnosticism demo — design

Date: 2026-06-20
Status: Approved (brainstorm)

## Goal

Prove, in the reference Argo deployment, that houba is **analyzer-agnostic** by running **two
different analyzers** side by side at the front door and reading both back **by digest**:

- **grype** — a vulnerability scanner → findings land in `vuln.*` (the SCAN axis).
- **regis** — a policy-as-code / governance tool → verdicts land in `policy.*` (the POLICY axis).

houba treats them identically: it `attach`es each one's SARIF as a signed referrer on the same
digest, and the classification (`vuln.*` vs `policy.*`) follows the SARIF `result.kind` alone — never
the tool name. The reference consumer (`blast-radius.sh`) then surfaces **both axes** as separate
columns, joined on the digest alongside owner and cluster.

This is the third decomposed piece of the "regis agnosticism" effort:

- Piece 1 (houba-core): SARIF `kind` → `policy.*` classification — **[houba#166](https://github.com/trivoallan/houba/pull/166), merged** (ADR 0039).
- Piece 2 (regis): `regis analyze --sarif` emits `kind:"fail"` on verdicts — **[regis#791](https://github.com/trivoallan/regis/pull/791), merged**.
- Piece 3 (this spec): the demo wiring both into the reference deployment.

Builds on the "SARIF at the front door" grype demo (`docs/superpowers/specs/2026-06-19-sarif-at-the-front-door-demo-design.md`, PR #165).

## What already ships

- The scan-attach Job (PR #165): an initContainer fetches the SBOM houba attached, grype scans it to
  SARIF, and a houba container `attach`es the SARIF as a signed referrer. Digest-pinned via
  `regctl image digest`; skips `bypassed/*`.
- `blast-radius.sh` joins owner + cluster by digest and renders a SCAN column from the scan referrer.
- houba#166: `kind`-bearing verdicts classify into `io.houba.scan.policy.*`; `kind`-less findings into
  `io.houba.scan.vuln.*`. regis#791: regis verdicts carry `kind:"fail"` + `security-severity`.

## The gap

The demo runs only **one** analyzer (grype), so it proves "a SARIF analyzer at the front door" but
not **agnosticism** (many analyzers, distinct axes, one consumer). `blast-radius` shows SCAN but no
POLICY axis, and its SCAN column re-parses raw SARIF by `security-severity` — which would miscount
regis `kind:"fail"` verdicts as vulnerability severities, contradicting houba#166.

## Design

### A second analyzer (regis) in the scan-attach Job

regis is multi-analyzer (grype/dockle/hadolint/trufflehog/licenses) and reads the **image**, not the
SBOM (unlike grype). So a new initContainer `regis` (off-the-shelf regis image) runs beside the
existing grype step:

```
regis analyze <ref@digest> --sarif > /shared/<key>.regis.sarif
```

To share one digest source across all steps, the existing `fetch` initContainer (houba image) also
writes `/shared/refs.tsv` — one `host  repo  tag  digest  key` row per placed image (the resolved
digest blast-radius reads). grype, regis, and the attach step all consume `refs.tsv`, so every step
pins the same digest.

The `attach` container then globs `/shared/<key>.*.sarif` and runs one
`houba attach <ref@digest> --report <file>` per file → **two referrers per digest** (grype + regis),
same artifactType (`application/vnd.houba.scan.result.v1`), different facts. The image digest is
never modified — both are referrers.

`scripts/scan-attach.sh` changes: the `fetch` mode emits `refs.tsv`; the `attach` mode loops the
per-tool SARIF files for each key instead of a single `<key>.sarif`. grype keeps reading the SBOM;
regis reads the image (registry pull + its own analyzer DBs).

### blast-radius gains a POLICY column, reads houba's computed facts

`blast-radius.sh` stops re-parsing raw SARIF and reads the **annotations houba already computed**.
For each digest:

1. Enumerate scan referrers — `regctl artifact list <ref> --filter-artifact-type
   application/vnd.houba.scan.result.v1 --format '{{json .}}'` (the invocation houba's own
   `list_referrers` adapter uses). Fall back to `regctl manifest get <ref>@<rdigest>` per referrer to
   read annotations if the descriptor doesn't carry them.
2. Sum across all referrers, **by fact space, not by tool**:
   - `io.houba.scan.vuln.{critical,high,medium,low}` → **SCAN**
   - `io.houba.scan.policy.{critical,high,medium,low}` → **POLICY**
3. Render each column `C{n} H{n} M{n} L{n}` (non-zero only), `clean` if a referrer exists but all
   zero, `-` if no referrer populates that space.

A referrer contributes to whichever axis its facts populate — grype → SCAN, regis → POLICY — so the
consumer is analyzer-agnostic, and adding an Nth analyzer needs no consumer change. This also fixes
the piece-1 SCAN re-parse (it now honours the houba#166 classification).

Table layout (POLICY inserted after SCAN):

```
REF(38)  OWNERS(26)  RUNNING IN(14)  SCAN(14)  POLICY(14)  BASE.DIGEST
```

### C4 + runbook + make

- **Deployment views** (`DeployReference` / `DeployLocal`): add regis as a **second instance** of the
  external analyzer system in the scan-attach Job pod, with its edges (image pull from the front-door
  registry + regis-data egress). The abstract Context / Container / Component / Hexagon views are
  **unchanged** — houba still only `attach`es; ingest-only is already modelled. Refresh the committed
  Mermaid exports.
- **Runbook** (`docs/how-to/reference-deployment.md`): `make scan` now runs grype **and** regis;
  `make blast-radius` shows SCAN (grype) + POLICY (regis). Narrate honestly — regis's **actual**
  governance verdicts on the placed images (EOL / hygiene / license, as `policy.*`), grype's CVEs as
  `vuln.*`, the bypass image `-` across **both** axes.
- No new MirrorPolicy example (the existing reference policy's placed images are analyzed by both).

## Deliberate simplifications (`ponytail:`)

- **regis pulls the image + its analyzer DBs** (egress is real), and needs insecure-registry config
  for Zot (tls off). The exact regis image, flags, and registry config are hardened in e2e — same as
  grype's container specifics were in piece 1.
- **`artifact list` enumeration** is validated against Zot; if it misbehaves (it was flaky in piece
  1's first cut), fall back to `regctl referrers`. This is the key e2e risk.
- **Two referrers, same artifactType.** blast-radius sums across all of them by fact space, so order
  and count don't matter; `attach`'s "newest wins" is irrelevant to the read.
- **No claim about specific regis counts** — the demo shows regis's real output; the robust,
  always-true lesson is the bypass image's total absence of provenance on both axes.

## Out of scope

- **Kyverno enforcement** (the admission policy example already exists; the demo stops at "read both
  axes by digest").
- **A third analyzer** — two is enough to prove agnosticism.
- **Any gating** — houba carries, doesn't gate (`--fail-on` is vuln-only and untouched).
- **houba-core changes** — none; pieces 1 & 2 shipped the classification and the regis output.
- **Rebuilt-with-provenance (index) images** — their referrers don't land on the resolved digest, so
  variant rows read `-` on both axes (the pre-existing referrer-durability gap, tracked separately:
  `houba-rebuild-referrer-durability`). The clean rows are the single-manifest path.

## Acceptance

- `make scan` → the scan-attach Job completes; each **single-manifest** placed image gains **two**
  scan referrers (grype + regis) on the unchanged digest (`regctl artifact list <digest>` shows both,
  with `io.houba.scan.vuln.*` and `io.houba.scan.policy.*` respectively).
- `make blast-radius` → SCAN shows grype's vuln buckets, POLICY shows regis's verdict buckets, and the
  bypass image shows `-` on both; e2e-validated on kind.
- `DeployReference` / `DeployLocal` show regis as a second analyzer in the scan-attach Job + its
  edges; Mermaid exports refreshed; abstract views unchanged.
- No change under `houba/` (deploy glue + scripts only).
