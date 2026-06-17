# Package-level SBOM

houba's provenance stamp carries **lineage** — `base.digest`, the transform steps, the owners.
Lineage answers *"which images derive from base X"*. But almost every real CVE is a **contents**
question: *"which images contain package P, and at which version?"* — and houba's own hardening
updates packages, so you cannot infer that from the base digest. A scan report does not fill the gap
either: a scan is *known-vulnerable as of its run date*, so it reads "clean" the day a zero-day drops.
Only a CVE-agnostic **SBOM** — an inventory of what is present — answers the contents question
retroactively, the instant a new CVE lands.

## What houba does

On **every image it places — copy *and* rebuild alike** — houba generates a package-level SBOM and
attaches it to the placed digest as an **OCI referrer**. The SBOM is produced by a standalone
[`syft`](https://github.com/anchore/syft) scan of the placed image (both paths know the digest at
that point), so coverage is uniform — there is no "rebuilt images only" gap. As the single front door
over every external image, houba is the natural choke point to guarantee **100% SBOM coverage**, which
is what *coverage gates value* demands.

Generation is **always-on**, governed by `HOUBA_SBOM_FORMATS` — a global operator setting, never a
per-policy field. It chooses *which* formats (SPDX by default; CycloneDX alongside or instead), never
*whether*. To enable CycloneDX see [Inspect an image's SBOM](../how-to/inspect-sbom.md); for the
variable itself, the [configuration reference](../reference/config.md).

## Presence, not yet trust

The SBOM is attached **unsigned**: its *presence* already answers the blast-radius query.
Cryptographically **signing** the SBOM under houba's identity is a separate, planned trust tier,
sequenced exactly as houba sequenced stamp-then-sign for the [signed attestations](attestations.md).
(Today the signed attestations cover the transform / provenance predicate, not the SBOM itself.)

## Known limit — bare-binary middleware

syft catalogs packages installed via OS package managers and language ecosystems — including
application dependencies nested inside JARs — with the purls that CVE feeds key on. A dependency
dropped in as a **bare binary** (`curl … -o /usr/local/bin/foo`) carries no package metadata and is
**not** captured. This is a documented, bounded limit, guarded explicitly by the depth acceptance test
rather than silently assumed away. houba's `rewritePackageSources` hardening nudges installs toward
the package-manager path (SBOM-visible) as a side effect, but cannot rewrite an upstream that fetches
a raw binary.

## What houba does not do

houba produces the queryable inventory; it never runs the query. CVE matching (`version → CVE-xxxx`)
and fleet-wide blast-radius live downstream in the org's observability stack — houba's standing
non-goal. For the mechanism rationale, see
[Architecture & design](https://github.com/trivoallan/houba/blob/main/docs/architecture/design.md)
and [ADR 0034](https://github.com/trivoallan/houba/blob/main/docs/architecture/decisions/0034-unify-sbom-on-syft.md).
