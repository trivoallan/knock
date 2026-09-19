---
title: "Gate between plan and apply"
description: "Every import, update and rebuild goes through an external verdict before knock applies it."
sidebar_position: 8
---

knock places nothing an evaluator has not seen. `reconcile --plan-out` writes a
[`ReconcilePlan`](../schemas/reconcile-plan.md): one entry per import, update or rebuild the run
would perform, each with the source digest to evaluate. The orchestrator evaluates
`{source}@{sourceDigest}` with the playbook of the policy's regime, **removes the refused
entries**, and runs `reconcile --apply-plan` on what remains. Absence is refusal.

```yaml title="docs/examples/gate/redis.yml" file=../../examples/gate/redis.yml
```

```json title="docs/examples/gate/plan.json" file=../../examples/gate/plan.json
```

What `--apply-plan` guarantees:

- an operation is applied only if an entry matches its policy, destination, tag, kind **and source
  digest**: an upstream re-push after the plan was written is withheld, never placed unjudged;
- a refused operation is reported `withheld` and touches nothing already placed: a refused update
  keeps the old digest in service, and a floating alias never moves onto a refused import;
- with `admit: true`, only approved placements are signed.

A `rebuild` is judged on its source digest; the rebuilt output is not evaluated before it is
placed. See the [design](https://github.com/trivoallan/knock/blob/main/openspec/changes/archive/2026-09-19-gate-between-plan-and-apply/design.md).
