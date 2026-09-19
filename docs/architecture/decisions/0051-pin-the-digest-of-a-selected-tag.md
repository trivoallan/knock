# 51. Pin the digest of a selected tag

Date: 2026-09-19

## Status

Proposed.

Narrows the gap [50. knock signs the image at admission](0050-knock-signs-the-image-at-admission.md)
accepts, for the source digest.

## Context

knock selects by tag and resolves tag → digest only when it plans. An orchestrator that evaluates
candidates by digest and derives a policy naming the admitted tags cannot stop knock from placing
(and, under `admit`, signing) a digest that upstream republished after the evaluation. A signature
is never removed, so a comparison after placement is too late.

## Decision

- **`tags.pins: {tag: digest}`**, an additive map on `TagSelection` (not a union type on `names`),
  so existing policies and schema consumers stay valid. A pin constrains a selected tag and never
  selects one.
- **Mismatch → withheld.** A pinned tag whose upstream digest differs is not imported, updated,
  signed or given a backfilled SBOM, and its alias is not re-pointed. It stays desired, so what is
  already placed is not deleted.
- **Match → no stability window.** The pin is the judgement the window stands in for.
- **`pin_mismatch`** is a countable report outcome (an `OperationKind` and a `Counts` field) that
  carries the observed and the pinned digest. It is not an error: it does not change the exit code.

## Consequences

- The first **withheld** plan entry: removed from the apply, desired set kept, reported apart. This
  is the seam the proposed gate between plan and apply needs.
- A pin judges the **source** digest. A rebuild's output digest is still signed under `admit`
  without a verdict on that output.
- No new port, adapter or C4 element.

Full change: [openspec/changes/archive/2026-09-19-pin-selected-tag-digest](../../../openspec/changes/archive/2026-09-19-pin-selected-tag-digest/proposal.md).
