# Migration-parity — demonstrable proof — design

Date: 2026-06-23
Status: Proposed (spec)

## Problem

The migration-parity *narrative* — "houba's `destinations` fan-out **replaces** registry
replication, and (because replication strips OCI referrers) keeps the SBOM/signature alive in
every team copy" — ships as prose (`docs/how-to/migrate-from-replication.md`, #156). But the
load-bearing claim (*the referrer survives into every copy*) is **asserted, not demonstrated**: all
eight `docs/examples/` policies fan out to a **single** destination, and no demo or test *shows* a
placed copy carrying its SBOM referrer. Under *the label is the product* / *coverage gates value*,
an adoption proof that cannot be **run** is not a proof. This is the lead *Now* item.

## Goal

Make the claim **demonstrable**: a runnable multi-destination fan-out where, after one
`houba reconcile`, **every** team copy is shown to carry its package-SBOM referrer (and, when a
signer is configured, its signature) — addressable by the same digest a CVE query already uses.

**Boundary — and the guardrail.** The demo proves houba's **positive**: *placement attaches the
referrer to every destination.* It does **not** stand up Harbor to demonstrate the **negative**
(replication stripping referrers) — that is an external, documented fact
([goharbor/harbor#23210](https://github.com/goharbor/harbor/issues/23210)), already cited in the
how-to. The demo registry is **Zot**, whose sync *does* propagate referrers, so the stripping
contrast cannot (and need not) be reproduced there. Any artifact that tries to reproduce Harbor's
stripping is out of scope.

## What already ships (≈ 70 %)

- **The narrative** — `docs/how-to/migrate-from-replication.md` (#156): jobs-parity table, the
  "referrers survive placement, not replication" section, an inline 2-destination YAML, a migration
  checklist.
- **Multi-`destinations` is a built feature** — `domain/mirror_policy.py` (`Defaults.destinations`
  / `ImportProfile.destinations`), fanned out in `use_cases/reconcile.py` (places + stamps + SBOMs
  each destination). **No houba-core code is needed.**
- **Referrer verification tooling** — `regctl` (the registry adapter) lists referrers;
  `cosign verify-attestation` verifies the signed tiers. The signed-SBOM tier exists
  (`HOUBA_ATTEST_SIGNER`, ADR 0029).
- **A reference deployment that is the demo** — kind + Zot + Argo App-of-Apps, with per-example
  `DEMO.md` narration (`docs/examples/reference/`).

## The gap

1. **No multi-destination example** — every example fans to one destination.
2. **No runnable proof** — nothing reconciles into 2+ copies and *asserts* the SBOM (and signature)
   referrer is present on **each**. The PR #142 `stick-test.sh` that prototyped this was never
   merged.

## Design — the proof

A single example fanned into two team projects, plus one script that reconciles it and asserts the
referrer landed on **both** copies. All under `docs/examples/` + `scripts/` + `docs/` — zero
houba-core.

| Leg | Question | How shown |
|-----|----------|-----------|
| place → fan-out | does one `reconcile` land the image in every team project? | both `team-a/*` and `team-b/*` resolve to the **same digest** |
| copy → SBOM | does each copy carry the package inventory? | `regctl` referrers on each digest shows an SPDX/CycloneDX artifact |
| copy → signature *(if signer set)* | is each copy verifiably from the front door? | `cosign verify-attestation` succeeds on each digest |

### Artifacts

1. **`docs/examples/migration/redis.yml`** — one source, `defaults.destinations` listing **two**
   team projects (e.g. `team-a` / `team-b`) in the demo Zot. Mirrors the how-to's inline YAML so the
   doc and the runnable example agree.
2. **`scripts/migration-parity-proof.sh`** — `regctl`-only, scenario-style like the existing
   fake-bins: `houba reconcile` the example, then for **each** destination resolve the digest and
   list referrers; assert a package-SBOM referrer is present; exit non-zero if **any** copy is bare.
   Prints a per-copy `SBOM present: team-a ✓ / team-b ✓` line — the thing a stakeholder reads.
3. **`docs/examples/migration/DEMO.md`** — narration tying the script output back to the how-to: two
   copies, both self-describing; replication would have stripped these (link the Harbor issue).

## Requirements

**Must-have (P0)** — the proof is not viable without these:

- **R1 Multi-destination example.** `docs/examples/migration/redis.yml` fans one import to ≥ 2
  destinations.
  - *Given* the example, *when* `houba reconcile` runs, *then* the same selected tag exists in
    every destination project at the **same digest**.
- **R2 SBOM-referrer assertion on every copy.** The proof script verifies each placed digest carries
  a package-SBOM referrer.
  - *Given* a placed copy, *when* its referrers are listed, *then* an SPDX **or** CycloneDX artifact
    is present — for **every** destination, not just the first.
  - *Negative:* *given* any destination whose copy lacks the SBOM referrer, *then* the script exits
    non-zero and names the bare copy.
- **R3 Runs on the existing demo substrate.** The script runs against the kind + Zot reference
  deployment (or a local Zot) with no new infrastructure.

**Nice-to-have (P1)** — fast follow:

- **R4 Signature assertion.** When `HOUBA_ATTEST_SIGNER` is configured, the script also asserts a
  cosign signature/attestation referrer on each copy (`cosign verify-attestation`). SBOM-only is a
  valid pass when no signer is set (the signed tier is independently demonstrated).
- **R5 Reference-deployment demo step.** Wire `migration-parity-proof.sh` into the demo flow / a
  `DEMO.md` step so it runs as part of the adoption walkthrough.

**Future (P2)** — design-compatible, not built now:

- **R6** A replication→`MirrorPolicy` importer (reads Harbor replication rules, emits `destinations`).
  This is the *Deferred* "Declaration scaffolding (⑥)" — keep the example/script shapes so an
  importer could target them later.

## Success metrics

- **Leading:** `scripts/migration-parity-proof.sh` exits **0** with `SBOM present` ✓ on **every**
  destination, locally and in CI; the how-to's inline YAML and the runnable example are byte-equal in
  spirit (doc-vs-example drift = 0).
- **Lagging:** in an adoption walkthrough, a platform/security stakeholder can run one command and
  see every team copy is self-describing — the migration-parity claim moves from "asserted in a doc"
  to "watched live."

## Non-goals

- **Reproducing Harbor's referrer stripping** (external fact; Zot propagates referrers anyway).
- **A replication-rule importer / codegen** (Deferred — ⑥).
- **Any houba-core change** — multi-`destinations` already ships.
- **A new external system or actor** — no `workspace.dsl` (C4) change; this composes existing
  houba + Zot + regctl/cosign.

## Open questions

- **Signer in the reference deployment** *(engineering)* — is `HOUBA_ATTEST_SIGNER` wired in the demo
  today? If yes, R4 is cheap and the proof covers both tiers; if not, P0 stays SBOM-only and R4 waits.
  *(non-blocking — R1–R3 stand alone.)*
- **Standalone vs demo-integrated** *(engineering/docs)* — land the script standalone first (P0),
  integrate into the demo walkthrough as R5? Proposed: yes.
- **Example registry projects** *(docs)* — reuse the demo Zot's existing project layout, or add
  `team-a`/`team-b` projects? Proposed: add two, matching the how-to's names.

## Timeline / sequencing

P0 (R1–R3) is the increment; R4–R5 are fast follows once a signer is confirmed. House obligations to
land **with** the implementation (per CLAUDE.md): the runnable example (R1), and a thin ADR under
`docs/architecture/decisions/` linking this spec. No C4 update (no actor/system change). The how-to
already exists; only a back-link to the runnable example is added.
