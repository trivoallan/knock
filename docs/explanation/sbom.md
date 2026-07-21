---
title: "Package-level SBOM"
description: "The inventory knock attaches to every placed image (copy and rebuild) so a CVE becomes one query, and why presence precedes signing."
sidebar_position: 4
---

knock's provenance stamp carries **lineage** — `base.digest`, the transform steps, the owners.
Lineage answers *"which images derive from base X"*. But almost every real CVE is a **contents**
question: *"which images contain package P, and at which version?"* — and knock's own hardening
updates packages, so you cannot infer that from the base digest. A scan report does not fill the gap
either: a scan is *known-vulnerable as of its run date*, so it reads "clean" the day a zero-day drops.
Only a CVE-agnostic **SBOM** — an inventory of what is present — answers the contents question
retroactively, the instant a new CVE lands.

## What knock does

On **every image it places — copy *and* rebuild alike** — knock generates a package-level SBOM and
attaches it to the placed digest as an **OCI referrer**. The SBOM is produced by a standalone
[`syft`](https://github.com/anchore/syft) scan of the placed image (both paths know the digest at
that point), so coverage is uniform — there is no "rebuilt images only" gap. As the single front door
over every external image, knock is the natural choke point to guarantee **100% SBOM coverage**, which
is what *coverage gates value* demands. Coverage is also self-healing: on every reconcile, a kept
digest missing its SBOM referrer is re-covered on the live digest without a rebuild, mirroring the
existing signature backfill (ADR 0039).

Generation is **always-on**, governed by `KNOCK_SBOM_FORMATS` — a global operator setting, never a
per-policy field. It chooses *which* formats (SPDX by default; CycloneDX alongside or instead), never
*whether*. To enable CycloneDX see [Inspect an image's SBOM](../how-to/inspect-sbom.md); for the
variable itself, the [configuration reference](../reference/configuration.md).

## Presence, then trust

The raw SBOM referrer answers the blast-radius query by its *presence* alone — it is attached on
every placed image, signed or not. When signing is configured (`KNOCK_ATTEST_SIGNER`, the **same**
identity that signs the transform and scan attestations), knock **additionally** signs each SBOM as
an in-toto attestation under its own identity, with the canonical predicate type
(`https://spdx.dev/Document` for SPDX, `https://cyclonedx.org/bom` for CycloneDX). A downstream
admission controller can then *require* a trustworthy SBOM with stock
`cosign verify-attestation --type spdxjson|cyclonedx`, exactly as it can require a signed transform or
scan. Presence is unconditional; trust rides the signer. See [signed attestations](attestations.md)
and [Inspect an image's SBOM](../how-to/inspect-sbom.md#verify-the-signed-sbom).

## Known limit — bare-binary middleware

syft catalogs packages installed via OS package managers and language ecosystems — including
application dependencies nested inside JARs — with the purls that CVE feeds key on. A dependency
dropped in as a **bare binary** (`curl … -o /usr/local/bin/foo`) carries no package metadata and is
**not** captured. This is a documented, bounded limit, guarded explicitly by the depth acceptance test
rather than silently assumed away. knock's `rewritePackageSources` hardening nudges installs toward
the package-manager path (SBOM-visible) as a side effect, but cannot rewrite an upstream that fetches
a raw binary.

## What knock does not do

knock produces the queryable inventory; it never runs the query. CVE matching (`version → CVE-xxxx`)
and fleet-wide blast-radius live downstream in the org's observability stack — knock's standing
non-goal. For the mechanism rationale, see
[Architecture & design](https://github.com/trivoallan/knock/blob/main/docs/architecture/design.md)
and [ADR 0034](https://github.com/trivoallan/knock/blob/main/docs/architecture/decisions/0034-unify-sbom-on-syft.md).
