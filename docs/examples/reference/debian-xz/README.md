# Incident reproduction — XZ backdoor (CVE-2024-3094)

This policy reproduces the **XZ backdoor** in the demo so the package-level blast-radius loop lights
up on a real incident. A deliberately-vulnerable fixture (`xz-utils 5.6.1-1`, built from a Debian sid
snapshot) is seeded into the demo registry as a pretend-upstream; this policy **rebuilds** it through
houba, so houba's SPDX SBOM captures `xz-utils 5.6.1-1` and Dependency-Track flags
`DEBIAN-CVE-2024-3094`.

**What this does NOT claim.** houba does **not** detect or block the backdoor — nothing did, pre-
disclosure. houba rebuilds faithfully; the value is that on disclosure day, *"which images ship
xz 5.6.0–5.6.1?"* is one query, including third-party images, because they came through the front
door with a signed package inventory.

**The contrast.** `bypassed/debian-xz` is the same vulnerable image pushed *directly* into the
registry — never through houba. It has no stamp and no SBOM, so the coverage report
(`make blast-radius`, the "⚠ carry NO houba stamp" line) flags it as the blind spot: what never came
through the mandated door is ungovernable.

Run it as part of the demo: `make local` (or `make demo`) seeds the fixture + bypass, reconciles this
policy, publishes the SBOM to Dependency-Track, then `make dt-vulns` populates OSV and `make dt-ui`
shows `demo/debian-xz` flagged.
