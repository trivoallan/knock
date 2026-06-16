# houba — Roadmap

*Format: Now / Deferred / Later. Status as of **0.6.0** (2026-06). The core loop is delivered, and the
single-front-door mandate is now **enforceable and trustworthy** — complete attestation coverage, a
`--fail-on` CI gate, and a frozen provenance contract have all shipped. Scan signal is now correct
across finding types (vulns vs. posture). The active frontier narrows to **scale hygiene**; the
remaining feature bets were deliberately cut or deferred (see *Deferred* / *Out of scope*).*

## Product thesis

houba is a **stamper**, not a query engine. It is the single front door through which external
container images enter your organization: it hardens them (internal CAs, internal package mirrors)
and stamps them with **standardized, portable provenance** — and, for rebuilt images, a
**package-level SPDX SBOM** (buildkit's native scanner). The value lands at incident time — when a
critical CVE drops, the stamp (lineage, ownership) and the SBOM (package inventory) turn *"which
images ship the vulnerable package, and who owns them?"* into one query in the tools you already
run. houba produces both facts; it never runs the query — still a stamper, not a query engine.

Two consequences drive everything below:

1. **The label is the product.** Because houba's value flows through the stamp *and the SBOM* into
   someone else's query tool, the provenance surface (the annotation schema + SPDX) is the public
   API. It must be standardized, portable, and trustworthy before anything else.
2. **Coverage gates value.** A stamp on 40 % of the fleet yields a blast-radius query with blind
   spots — useless in an incident. houba's value is proportional to it being the *mandatory* path
   for external images. This *was* the riskiest assumption — now **validated** (see below).

## Validated — the core bet holds (2026-06)

A platform / security team has **confirmed they would mandate houba as the single front door** for
external images. The riskiest assumption is answered *yes*: enforcement investment is now justified,
and *coverage gates value* moves from theory to a live requirement — the mandate is only worth as
much as houba covering 100 % of what enters. This drove the mandate-enforcement work now **delivered**
(see *Delivered — the mandate, made real*), and retired the standalone "assumption to validate" gate.

## Delivered — the core loop (Phases A/B + Phase C ①–⑤)

Phases A (pure `domain/` foundations) and B (all I/O adapters, composition root, runtime image) are
shipped. Phase C was deliberately **re-ordered against the inherited Groovy use-case list** — the
original plan put `product_import` last ("the big one"); under *the label is the product*, the order
inverts, schema-first. ①–⑤ are now all delivered:

| # | Outcome | Shipped as |
|---|---------|------------|
| ① | **Provenance schema — the public contract.** OCI-standard keys for standard facts, `io.houba.*` only for the novel (transform lineage). | `domain/stamp.py` |
| ② | **Derive-and-stamp engine** (the recast `product_import`). Transform *and* stamp; the stamp is the deliverable. | rebuild path in `use_cases/reconcile.py` |
| ③ | **Composable transform primitives.** `injectCA` / `rewritePackageSources` / `setTimezone` as declarative, pluggable steps — any org's scripts become *configuration*. | `domain/transforms/` |
| ④ | **Coverage audit — the verifiable front door.** "Show me images that do *not* carry the stamp." Makes the front door enforceable. | `houba audit` |
| ⑤ | **Lifecycle — `archive_purge`.** Delegated deletion + reference reaper + retention-driven soft-delete. `archive_restore` **rejected** (soft-delete already gives reversible removal). | `houba purge`, ADR 0017 |

Beyond the original 7 phases, also delivered: **signed SLSA / in-toto attestations** (rebuild path),
**`houba attach`** (scan ingestion → signed OCI referrers), and operational maturity — **in-pod
concurrency**, **cross-pod sharding**, **KEDA-driven buildkit autoscaling**, deb822 package sources,
cosign v3 signing-config, and a **single Argo reference deployment that is the demo** — one
App-of-Apps replaces the prior multi-overlay demo sprawl, so the demo *is* the adoptable blueprint
(six entry points → two; thesis-minimum operators, autoscaling an optional add-on). CLI verbs today:
`reconcile · purge · attach · audit · version · gc`.

## Delivered — the mandate, made real (the former *Now*)

The three gaps that made the front door **enforceable** and **trustworthy** are closed:

- **Complete attestation coverage.** Every path — copy, rebuild, and already-mirrored (backfill) —
  now carries a *signed* attestation, not just a stamp; the hole the coverage audit surfaced is shut.
  *(ADR 0019; closed #49 / #53)*
- **The front door can say *no*.** `houba attach --fail-on <severity>` turns scan ingestion into a CI
  gate — the first enforcement lever, not just observation. *(ADR 0021)*
- **The public contract is frozen.** `org.opencontainers.image.revision` now propagates the source
  image's revision and is omitted when undeclared — never fabricated from the digest or tag. The
  label is the API, and it no longer wobbles. *(ADR 0020)*

## Delivered — trustworthy coverage, registry parity, correct scan signal (2026-06)

All three former *Now* items are now resolved — two shipped as designed, the third **reframed and
shipped** once design exposed the real gap:

- **Signed-coverage audit tier.** `houba audit --signed` reports *signed* vs merely *stamped*, with
  `--fail-on-unsigned` as a CI gate — turning the verifiable front door (④) into a *trustworthy*
  one. Three-tier ladder: `uncovered < stamped < signed`. *(ADR 0026; closed #98)*
- **`attach` registry-config parity.** `houba attach` now drives the `HOUBA_REGISTRIES` roster
  (host-match + `--registry` override) like `reconcile` / `audit` / `purge`, via a shared
  `ensure_registry_session` helper — no more ambient regctl config. *(ADR 0025; closed #97)*
- **Scan ecosystem breadth — reframed to finding-type correctness.** The original "more format
  mappers" framing was a near-non-problem: Trivy already emits SARIF and `regis` will too. The real
  gap was *semantic* — the SARIF mapper counted every result as a vulnerability, so a `regis`
  posture report (pass/fail rules, EOL, hygiene) inflated `vuln.*` and tripped `--fail-on`. Now the
  mapper classifies rule evaluations as `rule.passed`/`rule.failed`, generically (no `regis`-specific
  code). *(ADR 0027; closed #102)*
- **Scan-referrer GC — the last feature-side item.** `houba gc` walks the roster and collects
  superseded scan-result referrers, keeping the N newest per `(tool, format)` older than a grace
  window (the same keep-N + older-than model proven on tag retention). Dry-run by default, `--apply`
  to delete; the decision is purely temporal (no usage oracle). *(ADR 0028)*

## Delivered — package-level blast-radius (SBOM, 2026-06)

The blast-radius promise now reaches **package** granularity, not just base-image lineage. Every
image houba **rebuilds** carries an **SPDX SBOM** that buildkit's native scanner generates during the
build — the inventory that answers *"which images ship the vulnerable package?"* for the common
incident (a CVE in a dependency, not the base). Depth validated empirically against the real
`buildkit-syft-scanner` (Log4Shell nested fat-JAR, Heartbleed/XZ OS packages, runtime/bare-binary
boundaries). Always-on on rebuild; mirrors the existing `provenance` flag. *(ADR 0029)*

## Now — finish the SBOM tiers + adoption

> Theme: the mandate is enforceable and trustworthy (see *Delivered*), and SBOM generation just
> lifted blast-radius to package level. The active frontier: finish the SBOM's coverage and trust
> tiers, and **adoption** — lowering the barrier to becoming the mandated front door.

- **`audit` "has SBOM" coverage dimension.** Report images that lack an SBOM, with a
  `--fail-on-no-sbom` gate — extending the verifiable front door to stamped → signed → has-SBOM.
  buildkit attaches the SBOM as an image-index attestation manifest, *not* an OCI referrer, so this
  needs an index-inspection probe rather than the `signed`-tier referrer mirror. *(ADR 0029, P0.5)*
- **Sign the SBOM** under houba's identity (cosign) — the trust tier, sequenced like stamp-then-sign.
  *(ADR 0029, P1)*

- **User documentation site.** Create and publish a user-facing docs site — getting-started,
  policy/config reference, the CLI verbs, and the provenance-stamp contract — built from the existing
  in-repo material (`README`, `docs/examples/`, the policy/scan schemas) and published on every merge
  to `main`. *The label is the product*, and a mandated front door only gets adopted if its users can
  self-serve; today that knowledge is scattered across the repo. The highest-leverage adoption item.

## Deferred — revisit only on a real signal (YAGNI until then)

These are not refused on principle — they are waiting for a concrete trigger that has not appeared:

- **More scan formats (CycloneDX, Trivy-native).** No transport gap exists today: Trivy emits SARIF
  and `regis` will. Add a mapper only when a scanner that emits *neither* SARIF shows up. A native
  `regis` mapper was likewise rejected in favor of `regis`-via-SARIF.
- **Declaration scaffolding (⑥) — `product_init` / `product_delete`.** CRUD ergonomics around the
  policy declaration. Build only when authoring friction is demonstrably the bottleneck.

## Later — directional

*(empty — the standing bets are either delivered, deferred above, or out of scope below.)*

## Explicitly out of scope

- **`proxycache_update` (⑦) — cut (decision closed).** Pure pass-through: no transform, no stamp, so
  it does not fit the stamper essence (*the label is the product*). It belongs in a separate tool, or
  nowhere. The formerly-open decision is now settled: out.
- **Runtime presence / fleet inventory.** houba stamps; it does not watch where its images run. The
  blast-radius query is assembled in the org's observability stack by reading the stamp. Closing that
  loop (native inventory, an operator) is a different, much larger product and is not on this roadmap.
- **Vulnerability store / continuous correlation.** houba emits signed scan *provenance* (the
  `attach` referrer, verified at admission — proof that *this digest came through the front door,
  signed*), not a vuln database. It never re-correlates a frozen package list against today's CVE
  feeds; that *currency* is the org's SBOM/vuln platform's job (e.g. Dependency-Track). The referrer
  is provenance, not a competing store — collapsing it into a store reopens the overlap. *(ADR 0032)*
- **End-of-life awareness.** Carried by a sibling tool (`regis`).
