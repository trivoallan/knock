# 35. Backstage coverage portal (TechInsights + Dependency-Track)

Date: 2026-06-17

## Status

Designed (brainstorm capture). Researched 2026-06-17: Harbor ≤2.15.x does **not** replicate OCI 1.1
referrers ([issue #23210](https://github.com/goharbor/harbor/issues/23210)) — absorbed by following the
digest to the attachment site.

Wires the Backstage integration deferred by [30. Multi-owner ownership](0030-multi-owner-ownership.md).
Builds on the both-paths SBOM referrer from [unify-SBOM-on-syft](0034-unify-sbom-on-syft.md) (PR #140).
Full design in [the spec](../../superpowers/specs/2026-06-17-backstage-coverage-portal-design.md).

## Context

houba stamps `io.houba.*` provenance and, on both copy and rebuild paths (#140), attaches a package
SBOM as an OCI referrer (SPDX or CycloneDX). The thesis — *coverage gates value* — needs a consumption
surface. The target architecture: houba **gates both entry namespaces** (official-catalog and
requested), so external entry coverage is structural; the *requested* project is then **replicated
into per-team namespaces** (Harbor internal fan-out, byte-for-byte). Earlier drafts wrongly modelled a
*replication back door* overwriting the stamp; corrected here.

## Decision

A **developer-scoped** Backstage surface, backed by a **TechInsights FactRetriever**, at the
**consumption point** (the team namespace):

- **The stamp survives replication, the referrers may not.** A byte-for-byte copy keeps the manifest
  (and its `io.houba` annotation) at the same digest, so provenance always rides the fan-out. The SBOM
  and cosign signature are repo-scoped OCI referrers — and **research (issue #23210) shows Harbor
  ≤2.15.x does not replicate OCI 1.1 referrers**, so they are absent in team namespaces (houba uses
  exactly that kind: syft SBOM referrer + cosign v3 bundle). Hence **two bars**: bar 1 = `stamped`
  (provenance, stable, the migration burndown); bar 2 = `SBOM + signature` — **computed at the
  attachment site by digest** (the digest is identical after replication), not per consuming namespace.
  No dependence on a Harbor fix; if a future Harbor replicates referrers, bar 2 collapses into bar 1.
- **Denominator = the entity's `FROM` refs**; numerator = stamped digests. **First-party images are
  excluded via the Backstage catalog** (an image that is a catalogued component's build output is
  first-party) — **no registry convention**, which the org cannot enforce at scale. The residue is
  human-triaged (request onboarding vs mark first-party), which also incentivizes cataloguing.
- **"Onboard" = an idempotent PR** against the MirrorPolicy repo routing a dark (legacy) external image
  through houba's **gated entry** (destination = the entry namespace; existing replication fans it
  out). **No "claim the path", no back-door checklist** — replication is the distribution mechanism,
  not a competitor. `owners` pre-filled from the requester (bootstrap); the usage oracle is the live
  blast-radius/purge truth.
- **The portal consumes `houba audit`** (supply side) and only adds the demand-side `FROM` scan — no
  registry credentials in Backstage. Bar 2 *is* `audit --signed` per namespace; #140 makes an
  `audit --sbom` referrer tier cheap.
- **Dependency-Track joined by digest** (`name=repo, version=digest`), on demand at card-click. Loading
  the SBOM into DT is out of houba's scope; #140 emits CycloneDX natively (format gap closed).

Adds `backstage` and `dependencyTrack` as External/Downstream software systems to the C4 model
(`workspace.dsl`; `_export/*.mmd` regen pending — no CI drift-check today).

## Consequences

- The "single front door" thesis is **measurable per service**, at the point where it can degrade
  (referrer loss in fan-out), and the gate enforces on the stable axis (stamped).
- The removed *realized/declared/contested* escape hatch and *claim-the-path* mechanism were solving a
  phantom overwrite — replication never strips the stamp. Simplified away.
- houba-side footprint = small: add `digest` to `audit`'s `CoverageOutcome` (join key) and an
  `--sbom` audit tier (bar 2); the `UsageOraclePort` widening is phase 2. Everything else is the
  external TypeScript plugin.
- Detection trusts stamp/referrer presence (no crypto verify) — same ceiling as `audit --signed`.
