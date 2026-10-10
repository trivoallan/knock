---
title: "Gate between plan and apply"
description: "Every import, update and rebuild goes through an external verdict before knock applies it."
sidebar_position: 9
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

See the [design](https://github.com/trivoallan/knock/blob/main/openspec/changes/archive/2026-09-19-gate-between-plan-and-apply/design.md).

## Judging what a rebuild produced

The plan lets an evaluator judge a **source** digest. For a policy that declares a `transform`,
the bytes worth judging are the ones knock builds. Give `--apply-plan` a staging registry and it
holds every rebuilt image there instead of placing it:

```bash
knock reconcile policies/ --plan-out plan.json
# evaluate each {source}@{sourceDigest}, remove the refused entries
knock reconcile policies/ --apply-plan plan.json --stage-to staging --staged-out staged.json
# evaluate each {staged}@{stagedDigest}, remove the refused entries
knock promote policies/ --staged staged.json
```

`staging` is a name from `KNOCK_REGISTRIES`. The run writes a
[`StagedRebuilds`](../schemas/staged-rebuilds.md) file: one entry per held image.

```json title="docs/examples/gate/staged.json" file=../../examples/gate/staged.json
```

What the two commands guarantee:

- a held image carries its stamp, its SBOM and its signed attestations in staging, and is **not
  signed as admitted**; its destination tag is left exactly as it was, and no alias moves onto it;
- copies are placed directly: a copied image is byte-identical to the source the plan judged;
- `promote` places only what the file still names, and trusts the file for nothing else. It checks
  that the policy declares the destination, that the staged repository is that destination under a
  registry of the roster, that the staged tag still resolves to the evaluated digest, and that the
  image's stamp names the entry's policy, import, variant and source digest;
- the image is copied **by digest with its referrers**, the SBOM and the signed attestation are
  looked for at the destination, and only then is the tag written. With `admit: true` the image is
  signed, and the aliases recorded in the entry follow;
- an entry that fails does not stop the others, and the command exits non-zero. Promoting the same
  file twice changes nothing. An image that is never promoted is planned again on the next pass.

**The staging registry must not be one consumers pull from.** knock refuses one that is also a
destination of the policy, and cannot know more. A registry that lives for the run is the simplest
form; it must hold every layer of the images rebuilt in one pass, base layers included. knock never
deletes from it. See [ADR 0055](https://github.com/trivoallan/knock/blob/main/docs/architecture/decisions/0055-stage-and-promote-rebuilds.md).
