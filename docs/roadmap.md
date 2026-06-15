# houba — Roadmap

*Format: Now / Next / Later. Status as of **0.5.0** (2026-06). The core loop is delivered; what
remains is completing coverage, firming the public contract, and turning the now-confirmed
single-front-door mandate into enforced coverage.*

## Product thesis

houba is a **stamper**, not a query engine. It is the single front door through which external
container images enter your organization: it hardens them (internal CAs, internal package mirrors)
and stamps them with **standardized, portable provenance**. The value lands at incident time — when
a critical CVE drops, the consistent provenance stamp turns *"what's our blast radius, and who owns
it?"* into one query in the observability stack you already run.

Two consequences drive everything below:

1. **The label is the product.** Because houba's value flows through the stamp into someone else's
   query tool, the provenance schema is the public API. It must be standardized, portable, and
   trustworthy before anything else.
2. **Coverage gates value.** A stamp on 40 % of the fleet yields a blast-radius query with blind
   spots — useless in an incident. houba's value is proportional to it being the *mandatory* path
   for external images. This *was* the riskiest assumption — now **validated** (see below).

## Validated — the core bet holds (2026-06)

A platform / security team has **confirmed they would mandate houba as the single front door** for
external images. The riskiest assumption is answered *yes*: enforcement investment is now justified,
and *coverage gates value* moves from theory to a live requirement — the mandate is only worth as
much as houba covering 100 % of what enters. This reprioritizes **Now** around making that mandate
real, and retires the standalone "assumption to validate" gate.

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
`reconcile · purge · attach · audit · version`.

## Now — make the mandate real

> Theme: with the single-front-door bet **confirmed** (see *Validated* above), the priority is a
> front door that is **complete** (coverage gates value) and **trustworthy** (the label is the
> product) — so the mandating team can actually rely on it. These are known, scoped gaps in what
> just shipped.

- **Complete attestation coverage.** Today only the *rebuild* path is signed; copied and
  already-mirrored (skipped) images carry the stamp but no signed attestation — a hole the coverage
  audit itself surfaces. Close it so every image houba fronts carries signed provenance.
  *(closes the known #49 / #53 gaps)*
- **Let the front door say *no*.** `houba attach --fail-on <severity>` turns scan ingestion into a
  CI gate — the first enforcement lever, not just observation.
- **Firm the public contract.** Resolve the one open schema question: what
  `org.opencontainers.image.revision` means for a *mirrored* image (today it maps to the source tag;
  OCI semantics say SCM commit). Decide before real artifacts depend on it — the label is the API and
  must not wobble.

## Next — breadth and the per-format registry

- **Scan ecosystem breadth.** Generalize `attach` beyond CVE: the **`regis` / EOL format mapper**
  (the sibling-tool integration that proves the per-format registry), plus **Trivy-native** and
  **CycloneDX** mappers.
- **`attach` registry-config parity.** Wire the `HOUBA_REGISTRIES` roster into `attach` as in
  `reconcile`, instead of relying on ambient regctl config.
- **Signed-coverage audit tier.** Extend `houba audit` to report *signed* vs merely *stamped*. Today
  it counts the annotation stamp; once *complete attestation coverage* (Now) lands, the audit can
  distinguish signed from unsigned provenance — turning the verifiable front door (④) into a
  *trustworthy* one. Gated on Now: until every path is signed, a signed-coverage number would
  mislead.

## Later — scaffolding, scale hygiene, directional

- **Declaration scaffolding (⑥).** `product_init` / `product_delete` — CRUD ergonomics around the
  policy declaration. Secondary; do when authoring friction is the real bottleneck.
- **Scan-referrer GC.** v1 accumulates referrers; retention / garbage-collection matters once volume
  does.
- **`proxycache_update` (⑦) — under review, leaning cut.** Pure pass-through: no transform, no stamp,
  so it does not fit the stamper essence. Likely belongs in a separate tool, or is dropped. Decision
  still formally open.

## Explicitly out of scope

- **Runtime presence / fleet inventory.** houba stamps; it does not watch where its images run. The
  blast-radius query is assembled in the org's observability stack by reading the stamp. Closing that
  loop (native inventory, an operator) is a different, much larger product and is not on this roadmap.
- **End-of-life awareness.** Carried by a sibling tool (`regis`).
