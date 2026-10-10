## Why

A `ReconcilePlan` entry does not say whether applying it builds an image or copies the source. An
orchestrator that wants to send a source to repair must know: approved as a copy, a source that
needed a rebuild is placed as it is. Today it would have to re-derive the answer from the policy,
where a transform is declared at three levels (`defaults`, import, variant), and a second
implementation of that merge can drift from knock's without a sound.

## What Changes

- Each `ReconcilePlan` entry gains `transformed` (boolean): true when the policy resolves a
  transform onto the operation, so applying it builds an image; false for a copy.
- The field is **not** part of what binds an approval. `--apply-plan` still matches an entry on
  policy, destination, tag, kind and source digest, and a plan filtered by a tool that drops the
  field still applies.
- The published JSON Schema, its reference page and the example plan carry the field. A plan
  written before this change still loads: the field defaults to false.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reconcile-gate`: the plan-writing requirement adds the `transformed` fact to each entry, and
  states that it does not bind an approval.

## Impact

- Code: `knock/domain/gate.py` (`PlannedOperation`), `knock/use_cases/reconcile_registry.py` (the
  plan is filled with the same expression that decides staging).
- Contract: `docs/reference/schemas/reconcile-plan.schema.json` and `.md`,
  `docs/examples/gate/plan.json`, `docs/reference/examples/gate.md`. Additive: no consumer breaks.
- No design document: one additive field, no new port, adapter or decision. ADR 0051 and ADR 0055
  stand as they are.
- Consumer: `uske` reads it to approve a source to repair only when knock says it rebuilds it.
