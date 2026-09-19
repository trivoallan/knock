## Why

Every refusal knock can issue today lands on a digest that has already been placed. Admission is
decided outside knock: an orchestrator evaluates candidate versions and derives a `MirrorPolicy`
that names only the admitted tags. That seam can only gate **imports**. Two of the four reconcile
operations place a digest that no verdict has seen:

- an **update**: the upstream tag moved (Docker Hub's official images are rebuilt under the same
  tags every time their base is refreshed), and knock re-imports after the 7-day stability window;
- a **rebuild**: the policy's transforms changed, so knock rebuilds everything it places.

A derived policy also has a sharp edge: a tag left out of it is outside the selection, so reconcile
purges it. Refusing an update by removing the tag deletes the version in service.

ADR 0050 (`spec.admit`) records the consequence: under `admit: true`, updates and rebuilds are
**signed** without a new verdict, "until the gate moves into knock". This change is that move.

## What Changes

- **The gate sits between reconcile's diff and its application.** Each import, update or rebuild
  that reconcile would perform goes through an external verdict before it is applied. A refusal
  withholds the operation and touches nothing already placed.
- **knock exposes the seam; it does not call the evaluator** (form b of the decision; the tradeoff
  is in `design.md`). Two new, mutually exclusive `reconcile` options:
  - `--plan-out FILE` computes the run with no mutation at all and writes a **reconcile plan**:
    one entry per import / update / rebuild, carrying the policy, the kind, the destination and
    tag, and the source repository, tag and **digest**.
  - `--apply-plan FILE` reconciles as usual, except that an import, update or rebuild is applied
    only when the file holds an entry with the same policy, destination, tag, kind and source
    digest. Every other one is reported as `withheld` and not applied.
  The orchestrator runs `--plan-out`, evaluates each entry (`regis` with the regime's playbook),
  removes the refused entries, and runs `--apply-plan` on what remains: the **filtered plan** is
  the same format, with fewer entries.
- **Admission becomes per operation under the gate.** With `--apply-plan` and `admit: true`, knock
  signs an image only when it was placed by an operation that the plan approved. The attestation
  backfill on an already placed digest attests but does not sign.
- **A new operation kind, `withheld`**, in the report (with its count). It appears only under
  `--apply-plan`.
- **The plan's JSON Schema** is derived from its Pydantic model and published under
  `docs/reference/schemas/reconcile-plan.*`.
- **`reconcile` without the new options is unchanged**, including the 0.10.0 meaning of
  `admit: true` (a policy-level assertion).

## Impact

- Domain: `knock/domain/gate.py` (the plan model, its schema, and the pure matching);
  `VariantReconcile.to_rebuild` in `knock/domain/reconcile.py` (the subset of `to_update` caused
  by a transform change).
- Ports: `OperationKind` gains `withheld`, `Counts` gains `withheld` (default 0, additive).
- Use cases: `reconcile_policies` / `RegistryPlanner` take an optional gate; `_apply_plan`
  records the planned operations, withholds unapproved ones, and signs only approved ones.
- CLI: `reconcile --plan-out` / `--apply-plan`. `make reference`.
- Git-sourced policies (skills) are not gated: they cannot be `admit`, and they place no image to
  evaluate. Their operations are not in the plan, and `--apply-plan` reconciles them as usual.
- No new port, adapter or external system. The C4 model is unchanged: the orchestrator and the
  evaluator stay outside knock, which reads and writes a file.
