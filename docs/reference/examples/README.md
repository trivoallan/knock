# Example policies

A catalog of runnable `MirrorPolicy` files, each demonstrating one knock capability against a
local registry. The files themselves live in [`docs/examples/`](../../examples/). New to knock?
Start with [Getting started](../../tutorials/getting-started.md), which walks the smallest
copy-path example end to end.

- [Reference policy](reference.md) — the reference policy the demo reconciles: copy (busybox) and rebuild (debian-tz) in one self-contained pass.
- [Redis: semver selection](redis.md) — semver selection and alias tracking over a real image (redis 7.2.x).
- [Hardened rebuild](hardened.md) — rebuild path with org hardening: inject internal CA, rewrite package sources.
- [Attested rebuild](attested.md) — rebuild path with signed in-toto attestations (SLSA + knock transform).
- [Repair rebuild](repaired.md) — rebuild path that upgrades OS packages from the internal mirror, on an operator-chosen epoch.
- [Pending-deletion (soft delete)](pending-deletion.md) — mark dropped tags with a pending-deletion referrer instead of deleting.
- [Retention](retention.md) — cap valid in-selection tags by keep-count and age.
- [Admission gate (Kyverno)](admission.md) — consumer-side Kyverno gate: admit only images with a fresh knock-signed scan attestation.
- [Gate between plan and apply](gate.md) — every import, update and rebuild goes through an external verdict before knock applies it.
