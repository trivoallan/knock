# Explanation

Understanding-oriented background: the why behind knock's design. The architecture deep-dive
lives in [`docs/architecture/design.md`](../architecture/design.md), the roadmap in
[`docs/roadmap.md`](../roadmap.md), and the decision records in
[`docs/architecture/decisions/`](../architecture/decisions/).

- [Architecture at a glance](architecture.md) — the hexagon, the two placement paths, and why the stamp + SBOM is the product: a narrative overview of how knock is built.
- [Features at a glance](features.md) — what knock does, organised by the product loop: place, stamp, inventory, sign, enforce, and reclaim, with links to the how-to and reference pages for each.
- [Transforms & signed attestations](attestations.md) — the hardening primitives and the SLSA / in-toto signing model.
- [Package-level SBOM](sbom.md) — the inventory knock attaches to every placed image (copy and rebuild) so a CVE becomes one query, and why presence precedes signing.
- [Deletion & retention](deletion-and-retention.md) — the two removal axes, and why knock marks (usage-gated) instead of hard-deleting.
- [How knock works](how-it-works.md) — what a `reconcile` run does step by step, and how the code is laid out.
