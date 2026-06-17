# Explanation

Understanding-oriented background — the *why* behind houba's design.

- **[Architecture & design](https://github.com/trivoallan/houba/blob/main/docs/architecture/design.md)** — the hexagonal layering, the ports and
  adapters, and why houba is a *stamper*, not a mirror.
- **[Deletion & retention](deletion-and-retention.md)** — the two removal axes and why houba marks
  (usage-gated) instead of hard-deleting.
- **[Transforms & signed attestations](attestations.md)** — the hardening primitives and the
  SLSA / in-toto signing model.
- **[Package-level SBOM](sbom.md)** — the inventory houba attaches to every placed image (copy and
  rebuild) so a CVE becomes one query, and why presence precedes signing.
- **[Roadmap & product thesis](https://github.com/trivoallan/houba/blob/main/docs/roadmap.md)** — "the label is the product", "coverage gates
  value", and what is built versus planned.
- **[Architecture decision records](https://github.com/trivoallan/houba/tree/main/docs/architecture/decisions)** — the design decisions, one ADR each.

For the case *for* adopting houba, see the landing page, **[Why houba](../index.md)**.
