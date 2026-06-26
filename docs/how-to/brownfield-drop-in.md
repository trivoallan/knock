---
title: "Drop houba into an existing Jenkins/skopeo/Harbor intake"
description: "Replace a skopeo→Harbor tag-only mirror with houba: same per-image policy, digest-pinned provenance, a declared owner label, and a signed SBOM inventory — so incident-time blast radius is one query."
sidebar_position: 10
---

# Drop houba into an existing Jenkins/skopeo/Harbor intake

:::note
This page is the decision view: the two queries and the honest pitch. The step-by-step `make demo-mongobleed` walkthrough is added alongside the demo.
:::

This is for a platform team that already mirrors external images (skopeo → Harbor) from a per-image YAML, adds OCI labels, and queries them in PowerBI/Datadog. houba replaces the intake step: same per-image policy, but every placed image now carries **digest-pinned** provenance, a first-class **owner** label, and a package **SBOM** — so the incident-time question becomes one query.

## The two queries, side by side

When a CVE drops you ask one question — *"which images ship the vulnerable package, and who owns them?"* — against two different datasets.

**Before (tag-only mirror, owner guessed from the repo path):**

```sql
-- joins on a mutable tag; owner is inferred from the project name, not a fact
SELECT image_tag, project_name AS guessed_owner
FROM mirror_inventory
WHERE image_tag LIKE '%mongo%';     -- which mongo? which digest? whose?
```

**After (houba: digest-pinned stamp + owner label + SBOM inventory):**

```sql
-- joins on the immutable digest; owner is read from io.houba.owners; package from the SBOM
SELECT digest, owners, package, version
FROM houba_inventory                -- one row per (digest, package) from the signed SBOM
WHERE package = 'mongodb-org-server'
  AND semver_in_range(version, '7.0.0', '7.0.27');  -- pseudo; adapt to your warehouse's version comparison
```

The diff between these two queries is the pitch.

## Ownership: declared once, digest-bound

houba does **not** discover owners. `io.houba.owners` is a value you declare **once**, in the policy, at the front door — and houba binds it to the image's immutable **digest**. The value of that is not "houba found the owner"; it is "the owner is declared once and is unambiguous forever, even when the same image shows up under two repos or a re-pointed tag." Pitch the capability honestly: *declared once, digest-bound, queryable* — a governance/discipline win, not magic identification. (The failure it prevents: the same image under two project paths yields two conflicting *guessed* owners "before"; one authoritative digest-pinned owner "after".)

## Why the SBOM inventory beats your scanner

Run your scanner against the official MongoDB image at a mongobleed-affected version:

```console
$ grype mongo:7.0.14 -o table | grep CVE-2025-14847   # (nothing)
$ trivy image --quiet mongo:7.0.14 | grep CVE-2025-14847   # (nothing)
```

Both report clean. But `mongodb-org-server` ships from MongoDB's **own apt repo**, not a distro feed — so neither scanner's CVE matcher fires on it. houba's syft SBOM **catalogs the package**, so the inventory query above finds the blast radius your scanners missed. That gap is exactly why a signed package **inventory** — not a scanner verdict — is what you query at incident time.

To find and fetch the SBOM behind that inventory query, see [Inspect an image's SBOM](./inspect-sbom.md).
