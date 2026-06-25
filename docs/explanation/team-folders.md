---
title: "Team folders and kargo"
description: "How a folder of MirrorPolicies becomes the unit of team ownership, and how per-team kargo pipelines isolate promotion outcomes with owner-attributed gate verdicts."
sidebar_position: 5
---

## The folder is the ownership boundary

A directory of `MirrorPolicy` files is the natural unit a team owns. Each file declares which
external images the team needs and where they land; the `owners` field on each import carries
one or more [Backstage entity-ref](https://backstage.io/docs/features/software-catalog/references)
strings (`group:default/platform`, `group:default/data`, …).

```yaml
# docs/examples/teams/team-platform.yaml (excerpt)
spec:
  imports:
    - name: base
      owners:
        - group:default/platform   # ← stamped as io.houba.owners on every placed digest
      destinations:
        - project: platform
          repository: busybox
```

When `houba reconcile` processes the folder, it stamps `io.houba.owners` onto every placed
digest. The blast-radius query can then join on that annotation to answer "which team owns the
images affected by CVE-X?" — the owner is carried in the image itself, not in a side-channel
spreadsheet.

## One pipeline per team

Each team's policy places to its own destination repository. That repository becomes the source
for its own kargo **Warehouse → Stage** pipeline, gated by the same `houba-scan-gate`
`AnalysisTemplate` the reference deployment uses.

```
Team A policy  →  houba reconcile  →  platform/busybox (registry)
                                             ↓
                                     kargo Warehouse (platform)
                                             ↓  AnalysisTemplate: houba verify --require scan-pass
                                     kargo Stage (platform/dev → platform/prod)


Team B policy  →  houba reconcile  →  data/debian-xz (registry)
                                             ↓
                                     kargo Warehouse (data)
                                             ↓  AnalysisTemplate: houba verify --require scan-pass
                                     kargo Stage (data/dev → data/prod)
```

The pipelines are structurally identical — they differ only in which repository they watch and
which team's images flow through them.

## Why isolation of outcomes matters

Two teams can reconcile from the same cluster at the same time. If Team A's image is clean, it
promotes. If Team B's image is vulnerable, its own gate holds it — Team A's pipeline is
unaffected. The gate verdict is always digest-bound and owner-attributed: the signed SARIF
attestation that `houba attach` writes carries the findings, and `houba verify` reads them to
produce a per-image pass/fail.

The XZ incident ([CVE-2024-3094](https://nvd.nist.gov/vuln/detail/CVE-2024-3094)) illustrates
this concretely. In the two-team demo:

- **team-platform** placed `busybox:1.37.0` — no critical CVEs → gate passes → image promoted.
- **team-data** placed `debian-xz:5.6.1` (the backdoored xz build) → 142 critical findings →
  `houba verify` exits 1 → kargo `AnalysisRun` fails → image held in `dev`, never reaches `prod`.

Each outcome is attributable to its owner (`io.houba.owners`): the blast-radius dashboard can
display "data team: 142 critical in `data/debian-xz`" without any manual triage.

## What `houba verify` actually checks

`houba verify` is the gate the `AnalysisTemplate` calls. It reads three categories of fact:

| Requirement | What it checks |
|---|---|
| `scan-pass` | signed in-toto scan attestation: signature valid, severity ≤ threshold, not stale |
| `stamp` | `io.houba.artifact.type` annotation present |
| `sbom` | at least one SPDX or CycloneDX OCI referrer attached |

The demo gates on `scan-pass`. Stamp and SBOM presence can be added with
`--require scan-pass,stamp,sbom`. All three live on the same digest — nothing extra to query.

## Honest scope of the demo

`make demo-teams` asserts the gate verdict via `houba verify` (the same binary the
`AnalysisTemplate` would call in a live promotion). It does not drive live kargo promotion
events: the reference stages themselves don't either — the demo wires the structural integration
(Warehouses + Stages exist, pipelines are gated) and proves the verdict is correct. A production
cluster with active promotions would see the `AnalysisRun` result propagate automatically; the
demo shows the verdict side, not the scheduler side.

## Further reading

- [Run the two-team demo](../how-to/demo-teams.md) — the runnable walkthrough
- [team-platform.yaml](../examples/teams/team-platform.yaml) + [team-data.yaml](../examples/teams/team-data.yaml) — the example policies
- [Gate a promotion or CI step with houba verify](../how-to/verify-gate.md) — the full `verify`
  reference
- [Transforms & signed attestations](attestations.md) — how the scan attestation is produced
