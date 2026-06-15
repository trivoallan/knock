# houba — Roadmap

*Format: Now / Next / Later. Status as of **0.5.0** (2026-06). The core loop is delivered; what
remains is completing coverage, firming the public contract, and the enforcement bet.*

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
   for external images. This is the riskiest assumption (see **Now → validate the bet**).

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
cosign v3 signing-config. CLI verbs today: `reconcile · purge · attach · audit · version`.

## Now — finish what the core loop started

> Theme: **firm the contract** (the label is the product) and **close coverage holes** (coverage
> gates value). These are known, scoped gaps in what just shipped.

- **Validate the bet *(discovery, not eng — do this first)*.** The riskiest assumption is that a
  platform/security org will actually *mandate* a single front door for external images. Cheapest
  test: ask one such team whether they *would impose* it. If yes, there is a product; if "we'll
  never get it enforced," the stamp covers a fraction of the fleet and houba is a feature, not a
  tool. Run this before investing further in enforcement.
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
