# SBOM generation on the rebuild path — design

*Status: design. Roadmap item: **new Now → "SBOM generation — package-level blast-radius"**
(reopens the package-level gap the roadmap's "feature-complete" claim implicitly closed by scoping
blast-radius to base-image level). Date: 2026-06-16.*

## Why

knock's value lands at incident time, through one blast-radius query — *the label is the product*.
But the provenance stamp carries **lineage** (`base.digest`, `transform.steps`, `owners`), not
**contents**. Lineage answers *"which images derive from base X"*; it cannot answer *"which images
contain package P"* — and almost every real CVE is a content question. Worse, knock's own hardening
(`rewritePackageSources`) updates packages, so you cannot even infer package versions from
`base.digest`. The stamp, alone, answers the rarest incident class and is blind to the common ones.

A scan report (`knock attach`) does not fill this gap: a scan is *known-vulnerable as of its run
date*. On the day a zero-day drops, every prior scan reads "clean" because the CVE did not exist yet.
Only an **SBOM** — a CVE-agnostic inventory of what is present — answers *"which images contain P"*
retroactively, the instant a new CVE lands.

knock is the single front door, so it is the one place that sees every external image exactly once,
at entry, on bytes it controls (99% of intake is rebuild). That makes it the natural choke point to
guarantee **100% SBOM coverage** — what *coverage gates value* demands — versus the best-effort,
opt-in, async coverage a registry scanner gives.

Goal: **every image knock rebuilds carries a portable SPDX SBOM**, deep enough to surface
application-layer dependencies (nested JARs), attached as a referrer, so the org's observability
stack can answer package-level blast-radius at incident time.

## Empirical validation (the risk was depth — it is retired)

The one real risk was *"is buildkit's native scanner deep enough?"* Replayed the incident table
against the **real** `docker/buildkit-syft-scanner:stable-1` (syft-for-buildkit v1.11.0), via a
buildkit SBOM build of a `debian:bookworm-slim` image carrying a Spring Boot fat-JAR with
`log4j-core 2.14.1` nested under `BOOT-INF/lib/`:

| Incident | Layer | SBOM result (real scanner) | Blast-radius |
|---|---|---|---|
| **Log4Shell** CVE-2021-44228 | Java app, nested fat-JAR | `log4j-core 2.14.1` — `pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1` | answerable |
| **Heartbleed** CVE-2014-0160 | OS pkg (openssl) | `openssl` + `libssl3 3.0.20` — `pkg:deb/...?upstream=openssl` | answerable |
| **XZ backdoor** CVE-2024-3094 | OS pkg, version-precise | `liblzma5 5.4.1-1` — `pkg:deb/...?upstream=xz-utils` | answerable |
| **Leaky Vessels** CVE-2024-21626 | host runtime (runc) | **absent** | correctly out of scope |

The scanner emits **purls** — the exact identifiers CVE feeds key on — including the deb
`upstream=` source-package mapping (so a query against `xz-utils` finds the installed `liblzma5`).
Depth, OS-package precision, and the runtime boundary all hold. The specific versions present happen
to be patched; irrelevant — the test proves *capture and queryability*, not vuln presence. The CVE
*match* (`version → CVE-xxxx`) stays downstream in the org's stack; knock produces the queryable
inventory, nothing more.

## Known coverage limit — bare-binary middleware

Replaying a **middleware** category against the same real scanner exposes the one structural blind
spot, and it is an *install-method* gap, not a depth gap:

| Middleware entered via | SBOM result | 
|---|---|
| package manager (`apt`/`apk`, official images that drop `mongodb-org`/`redis` debs) | captured — `pkg:deb/...?upstream=...`, like any OS package |
| language ecosystem (JAR / npm / wheel) | captured — like the nested Log4Shell JAR |
| **bare binary** (`curl …-o /usr/local/bin/mongod`, `tar xz`) | **absent** — no package metadata; the filename is irrelevant, syft matches by content signature |

So a MongoDB-class CVE is blast-radius-answerable **iff** the middleware arrived via package or
language ecosystem; a `curl|tar`'d binary in an upstream Dockerfile is invisible. Mitigations are
partial and not relied upon: syft ships content classifiers for a curated set of server binaries
(redis, nginx, postgres, node, go, haproxy…), so *some* bare binaries are still caught — coverage of
any specific one depends on the pinned scanner version (verify, do not assume). And knock's own
`rewritePackageSources` hardening pushes installs toward the package path (SBOM-visible) as a side
effect — but cannot rewrite an upstream that fetches a raw binary. **This is a documented, bounded
limit, not engineered around in v1.** The CI acceptance matrix records it explicitly (a bare-binary
middleware fixture asserted *absent*, so the gap is visible, not silently assumed covered).

## The unifying rule

knock already enables buildkit's native **provenance** attestation via one flag
(`BuildRequest.provenance` → `--opt=attest:provenance=mode=max`), attached as a referrer at push.
**SBOM is the same shape:** one flag, attached for free at push. No new port, no new adapter, no
extraction pipeline for *presence*.

This splits cleanly along knock's own coverage ladder (`uncovered < stamped < signed`):

| Tier | What | Priority |
|---|---|---|
| **present** | buildkit attaches the SPDX SBOM referrer at push | **P0 — answers blast-radius** |
| **signed** | knock cosign-signs the SBOM under its identity | **P1 — the trust layer** |

The present-but-unsigned SBOM already delivers the promise (answer the query). Signing is the
*trustworthy* tier — sequenced exactly as knock sequenced stamp-then-sign for the annotation.

## 1. The flag (`ports/image_builder.py`, `adapters/buildkit_cli.py`)

- `BuildRequest` gains `sbom: bool = False`, one-for-one with `provenance`.
- `BuildkitAdapter.build_and_push` appends `--opt=attest:sbom=true` when set, right beside the
  existing `attest:provenance` branch. ~3 lines, identical pattern.

## 2. Wiring (`use_cases/reconcile.py`)

The rebuild path already builds `BuildRequest(..., provenance=provenance)` (~line 175) and sets
`provenance=attestor is not None` (~line 425). Add `sbom=True` on the rebuild branch.

- **Decided (2026-06-16): always-on for rebuild** — `sbom=True` is set unconditionally on the
  rebuild branch, *not* gated on the attestor (unlike `provenance`) and with no config toggle.
  *Coverage gates value* — an optional SBOM defeats the mandate the moment one team forgets the flag.

## 3. Audit dimension (`use_cases/audit.py`) — deferred to a follow-up

Intent: a *"has SBOM"* coverage dimension + `--fail-on-no-sbom`, so the verifiable front door reads
stamped → signed → **has SBOM**.

**Empirical correction (2026-06-16):** this is *not* a mirror of the `signed` probe. buildkit
attaches the SBOM as an **image-index attestation manifest** (the `unknown/unknown` index entry,
annotated `vnd.docker.reference.type=attestation-manifest`), **not** an OCI subject-referrer. So
`audit`'s `list_referrers(ref, …)` will not find it. Detecting coverage requires *reading the image
index* for an attestation-manifest entry (and confirming its predicate is SPDX) — a new
`RegistryPort` capability, not a one-line probe. Larger than §1–§2; ships as its own follow-up,
after §1–§2 deliver the SBOM itself.

## 4. Cost & the copy-path ponytail

- Rebuild SBOM generation runs inside the build buildkit already does — near-zero marginal cost,
  and maximally accurate (buildkit *observed* the build; no inference).
- **Copy path (~1% of intake): no SBOM.** There is no build to observe; generating one means
  pull + syft, a separate heavyweight op.
  - *ponytail: copy-path images get no SBOM; the audit "has SBOM" dimension flags them. Build the
    pull+syft path (`SbomGeneratorPort` → `SyftAdapter`, propagate-upstream-or-generate, mirroring
    the `.revision` propagate-or-omit rule) only when copy-path volume is a demonstrated problem.*

## Scope

**P0 (MVP-feature — does what it promises):** the flag (§1), rebuild wiring always-on (§2), and the
incident matrix as a CI acceptance gate (Testing). These deliver the SBOM on every rebuild — the
actual blast-radius value.

**P0.5 (fast-follow, same theme):** the `audit` "has SBOM" dimension (§3) — deferred because
detecting the index-embedded SBOM needs an index-inspection probe, not the referrer mirror first
assumed.

**P1 (trust tier, fast-follow):** cosign-sign the SBOM under knock's identity, slotting into the
existing `signed` ladder. The present-but-unsigned SBOM already answers blast-radius; signing
protects the inventory from tampering.

**Out of scope (P2 / YAGNI):**
- Copy-path SBOM generation — the `# ponytail:` above; build at a real volume signal.
- CycloneDX / alternate formats — buildkit emits SPDX natively; add a format only when a consumer
  demands one buildkit does not emit.
- SBOM backfill on already-mirrored images — the attestation-coverage idempotent-backfill pattern
  applies, but YAGNI for MVP.
- The blast-radius **query engine** / CVE matching / runtime fleet inventory — downstream in the
  org's observability stack, knock's standing non-goal.

## Decisions ratified (2026-06-16)

1. **Signing is P1, not P0.** The unsigned buildkit-native SBOM answers the blast-radius query; the
   cosign-signed tier is a fast-follow that slots into the existing `signed` audit ladder, sequenced
   like stamp-then-sign. P0 ships the SBOM *present*; signing follows in its own change.
2. **Always-on, no config toggle** (see §2). Every rebuild emits an SBOM unconditionally — coverage
   gates value, an optional SBOM defeats the mandate.

## Resolved during design (2026-06-16)

- **SBOM attachment mechanism.** Inspecting a real buildkit SBOM build settled the former §3 open
  question: buildkit embeds the SBOM as an **image-index attestation manifest**
  (`vnd.docker.reference.type=attestation-manifest`), not an OCI referrer. There is no "referrer
  media type" to probe — the `audit` dimension (§3) must read the image index instead, which is why
  it moved to a fast-follow. Does not block §1–§2.

## Testing (TDD)

- **Adapter (`tests/integration`, fake-bin `buildctl`):** `sbom=True` ⇒ argv contains
  `--opt=attest:sbom=true`; `sbom=False` ⇒ it does not. Assert via `FAKE_BUILDCTL_LOG`.
- **Use case (fakes):** the rebuild branch sets `sbom=True` on the `BuildRequest` handed to
  `FakeImageBuilder`; the copy branch never does.
- **Audit (fakes):** "has SBOM" dimension counts SBOM-referrer-present vs absent via seeded
  `FakeRegistry.list_referrers`; `--fail-on-no-sbom` reddens the exit when any image lacks one.
- **Acceptance gate — the incident matrix (`tests/integration`, real buildkit, opt-in marker):**
  build the fat-JAR-on-debian fixture, run buildkit SBOM, assert the extracted SPDX **contains**
  `log4j-core` (nested), `libssl3`/`openssl`, `liblzma5`, and `redis-server` (middleware via
  package) — each with version+purl — and **does not contain** `runc` (host runtime) nor a
  bare-binary `mongod` (the documented middleware blind spot, asserted absent so the gap stays
  visible). This is the permanent guard against silent regression — it must run against knock's
  actual buildkit scanner config, not standalone syft.

## Docs to sync (same change as ship)

- ADR mirror: [0029-sbom-generation.md](../../architecture/decisions/0029-sbom-generation.md).
- C4 model: **unchanged** — no new port, adapter, actor, or external system. The
  `buildkit-syft-scanner` is internal to buildkit's operation (like its provenance generator,
  which carries no C4 node); knock only passes a flag. Reuses `ImageBuilderPort` / `RegistryPort`.
- `docs/examples/`: refresh an `attested`/SBOM example to show the SBOM referrer once it exists
  (conditional, like the attestation-coverage spec) — no new `MirrorPolicy` field, so no policy
  example to add; this is a build-time flag, not policy.
- Roadmap: add the new *Now* item "SBOM generation — package-level blast-radius"; this brainstorm
  showed the prior "feature-complete" claim held only at base-image granularity.
