# Proposal

## Why

The rebuild path mixes two gestures in one `transform:` list. Hardening (`injectCA`,
`rewritePackageSources`, `setTimezone`) is a placement invariant applied whatever the verdict.
Repair (`upgradePackages`, ADR 0054) only makes sense when a verdict asked for it, yet today it runs
on every selected tag and fires when a human edits `epoch` in the policy. A fixable OS-package CVE
found by an evaluator on one digest triggers nothing by itself.

This is the knock side of the cross-repo change `split-knock-policy-transform-remediate` (workspace
`openspec/`), decided on 2026-10-16. ADR 0051 forbids knock from knowing who judges: the order comes
from the orchestrator through the plan file, and knock only applies it.

## What Changes

- **BREAKING** A policy has two step lists, `transform:` (always applied) and `remediate:` (applied
  only on order, per plan operation). `transform:` refuses `upgradePackages`; `remediate:` accepts
  `upgradePackages` and `rewritePackageSources`.
- **BREAKING** `upgradePackages` loses its `epoch` parameter. The epoch comes with the order.
- A `ReconcilePlan` operation gains an optional `remediate: {epoch}` order (outside the key) and an
  informative `remediated` flag.
- Only operations carrying an order are staged; without `--stage-to`, such an operation is withheld.
- The remediation is recorded apart from the transform version (stamp annotations, predicate field
  `remediation {steps, epoch}`), so the next pass does not undo it.
- `--applied-out` writes an `AppliedOperations` document: source → written digest, and withheld
  operations with their reason.
- ADR 0054 is revised.

## Capabilities

### New Capabilities
- `policy-remediation`: the `transform:` / `remediate:` split, remediation orders in the plan, their
  staging, provenance and reporting.

### Modified Capabilities
- `reconcile-gate`: an approved operation can be withheld for a stated reason.

## Impact

`knock/domain/mirror_policy.py`, `knock/domain/transforms/` (steps, render, schema),
`knock/domain/gate.py`, `knock/domain/reconcile.py`, `knock/domain/stamp.py`,
`knock/domain/attestation.py`, `knock/use_cases/reconcile_registry.py`, `knock/cli/` (reconcile),
published schemas, `docs/reference/`, `docs/examples/`, ADR 0054, `TODOS.md`. Policies using
`upgradePackages { epoch }` must migrate; each consumer moves its pin and its policies in one PR.
