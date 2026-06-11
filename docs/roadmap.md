# houba — Roadmap

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
   for external images. This is the riskiest assumption (see below).

## Status

- **Phase A (delivered)** — foundations, complete pure `domain/` layer (> 90 % coverage), read-only
  Harbor / source-registry adapters, `houba dev capture`.
- **Phase B (delivered)** — all I/O adapters (BuildKit, git, GitLab, Teams), Harbor write-side,
  composition root, runtime image bundling skopeo + buildctl + git.
- **Phase C (current)** — the derive-and-stamp engine, re-scoped below.

## Phase C — ordered by the thesis, not by the inherited Groovy use-case list

The original plan put `product_import` last ("the big one"). With *the label is the product*, the
order inverts.

### ① Provenance schema — the public contract *(new)*

The first thing to freeze, because it is the API. Decisions to make here:

- Emit **standard OCI annotations** for standard facts (`org.opencontainers.image.source`,
  `.revision`, `.base.name`, `.base.digest`, `.created`) so any scanner/registry reads them for free.
- Reserve the `io.houba.*` namespace **only** for the genuinely novel: the transformation lineage
  (which policy, which version).
- Carry heavy provenance as **SLSA / in-toto attestations**, not ad-hoc labels.
- Stamp a **stable key** (a product / team identifier), never the mutable human owner — the owner is
  resolved downstream at query time by joining that key to a directory/CMDB. Immutable build facts
  on the artifact; mutable org facts stay out.
- Refactor `houba/domain/labels.py`: today it emits `io.houba.*` for *everything*; split into
  standard-vs-novel per the above.

### ② Derive-and-stamp engine *(= the former `product_import`, recast)*

The core verb, promoted to second. Transform (inject CA, rewrite repos) **and** stamp. The
transformation is the means; the stamp is the deliverable.

### ③ Composable transformation primitives

Generalize the hardening steps into declarative, composable primitives — `inject-ca`,
`rewrite-package-sources`, `set-label`, `set-timezone` — of which any one organization's scripts are
a *configuration*, not hardcoded behavior. This is the essentialization step.

### ④ Coverage audit *(new)*

"Show me the images in the registry that do **not** carry houba's stamp" — a coverage-gap report.
This is what makes the front door *verifiable*, and therefore enforceable. Without it, "mandatory
front door" is a wish.

### ⑤ Lifecycle — `archive_purge` / `archive_restore`

Retention. Real, but after the core loop.

### ⑥ Scaffolding — `product_init` / `product_delete`

CRUD around the declaration. Secondary.

### ⑦ `proxycache_update` — under review / candidate to cut

Pure pass-through, no transform, no stamp. It does not fit the stamper essence. Likely belongs in a
separate tool, or is dropped.

## The assumption to validate before investing in Phase C

**Will a platform/security org actually mandate a single front door for external images?** The
cheapest test: ask one such team whether they *would impose* it. If yes, there is a product. If "we
will never get it enforced," the stamp covers a fraction of the fleet and the product is a feature,
not a tool. Validate this before building, not after.

## Explicitly out of scope

- **Runtime presence / fleet inventory.** houba stamps; it does not watch where its images run. The
  blast-radius query is assembled in the org's observability stack by reading the stamp. Closing that
  loop (native inventory, an operator) is a different, much larger product and is not on this roadmap.
- **End-of-life awareness.** Carried by a sibling tool (`regis`).
