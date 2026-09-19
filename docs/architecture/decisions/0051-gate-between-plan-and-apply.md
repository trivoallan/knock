# 51. The gate between reconcile's plan and its application

Date: 2026-09-19

## Status

Proposed.

Builds on [50. knock signs the image at admission](0050-knock-signs-the-image-at-admission.md):
closes the gap its consequences name (updates and rebuilds signed without a new verdict).

## Context

Admission is decided outside knock, by an orchestrator that derives a policy naming only the
admitted tags. That seam gates imports only: an update (upstream re-pushed a tag) and a rebuild
(the transforms changed) place a digest no verdict has seen, and a tag left out of the derived
policy is purged. The gate belongs between reconcile's diff and its application. Two forms fit:
knock calls the evaluator itself (a), or knock exposes the seam and the orchestrator calls the
evaluator between two runs (b).

## Decision

- **Form (b).** knock does not know who judges. Form (a) would need an evaluator port and adapter,
  and the regime-to-playbook mapping inside knock, which the policy deliberately does not carry.
- **`reconcile --plan-out FILE`** places nothing and writes a `ReconcilePlan`: one entry per
  import / update / rebuild with the policy, destination, tag, and source repository, tag and
  digest. Its JSON Schema is derived from the model and published.
- **`reconcile --apply-plan FILE`** applies an import, update or rebuild only if the file holds an
  entry with the same (policy, destination, tag, kind, source digest). Others are `withheld`:
  not applied, destination untouched. The filtered plan is the plan minus the refused entries.
- **Under `--apply-plan`, `admit: true` signs only approved placements**; the attestation backfill
  attests without signing. Plain `reconcile` keeps ADR 0050's meaning.

## Consequences

- An approval is bound to a digest: drift between the two runs withholds, never places unjudged.
- A refusal never shrinks the selection, so it never purges a version in service.
- A rebuild is judged on its source digest; judging the rebuilt output needs a closed transit.
- The plan file is a public contract, versioned by its `apiVersion`.
- No new port, adapter, external system or C4 actor: the orchestrator and evaluator stay outside
  knock, which reads and writes a file.

Full change: [openspec/changes/archive/2026-09-19-gate-between-plan-and-apply](../../../openspec/changes/archive/2026-09-19-gate-between-plan-and-apply/proposal.md)
([design](../../../openspec/changes/archive/2026-09-19-gate-between-plan-and-apply/design.md)).
