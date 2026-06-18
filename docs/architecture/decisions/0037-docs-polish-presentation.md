# 37. Docs polish — published architecture narrative + deck

Date: 2026-06-18

## Status

Accepted

## Context

The docs site is Diátaxis-complete but the architecture story lives only in `docs/architecture/`,
which is excluded from the published site, and no diagram renders on the public site. The roadmap's
adoption frontier needs a self-serve surface good enough to onboard without us.

## Decision

- Publish a narrative **Architecture at a glance** Explanation page; `design.md` + the C4 model stay
  the GitHub deep-dive, linked for depth (single source for rationale preserved).
- Diagrams are **hand-authored narrative Mermaid**, not the committed Structurizr C4 exports — the
  exports are auto-generated and verbose, and embedding them is sync debt. They stay linked only.
- The architecture presentation also ships as a standalone **slidev deck** under `presentation/`,
  built on demand (no CI wiring).
- Example walkthroughs are **consolidated into how-to / explanation** guides (no per-example
  READMEs), keeping `examples/` the runnable catalog and respecting Diátaxis.

## Consequences

- The published site gains an architecture narrative and rendered diagrams.
- A new how-to documents the rebuild/harden path (previously task-undocumented).
- No `workspace.dsl` / C4 model change: the narrative diagrams are a redraw of the existing model.

Full spec: [docs/superpowers/specs/2026-06-18-docs-polish-pass-design.md](../../superpowers/specs/2026-06-18-docs-polish-pass-design.md)
