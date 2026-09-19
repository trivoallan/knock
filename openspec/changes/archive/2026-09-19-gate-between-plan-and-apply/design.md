## Context

`reconcile` already separates a side-effect-free diff from its application: `reconcile_import`
(pure) turns source and mirror state into `to_import` / `to_update`, and the use case applies them
per policy, in isolation. The gate goes between those two steps. The decision this change
implements (D-30 in the supply-chain dossier) allows two forms:

- **(a)** knock calls the evaluator itself, per operation, before applying it;
- **(b)** knock only exposes the seam: it writes the plan, then applies a filtered plan, and the
  orchestrator calls the evaluator in between.

## Decision 1: form (b), a plan file

### The tradeoff

**(a) couples knock to an evaluator.** knock would need to know how to invoke one (`regis
analyze <ref> --playbook <path>`), how to read its verdict, and which playbook applies to which
policy. The last one is the problem: the playbook follows the policy's *regime*, a governance fact
the dossier deliberately keeps out of `MirrorPolicy` (D-21 rejected a `playbook` field because it
would change knock). Form (a) needs a port (`EvaluatorPort`), an adapter per evaluator, a fake-bin,
a regime-to-playbook mapping in knock's configuration, and a failure mode for "the evaluator did
not conclude" (D-23: fail closed, and record it). It also puts a slow external scan inside the apply
phase, where knock's concurrency and error isolation were designed around registry calls.

**(b) costs a file contract and a second pass.** The plan is a public format that must stay stable,
and the world can move between `--plan-out` and `--apply-plan`: an upstream tag can be re-pushed,
a mirror tag can change. That drift is the real risk of (b), and it is closed by construction
(Decision 3): an approval is bound to a source **digest**, never a tag, so drift can only withhold,
never place something unjudged. The second pass costs one more round of registry reads per policy.

### Choice: (b)

- knock stays ignorant of **who** judges, the way `attach` ingests any SARIF producer and nothing in
  it is specific to one scanner. The evaluator, the playbook choice (D-21), the refusal journal
  (D-22) and the "no conclusion" state (D-23) stay in the orchestrator, which already owns them.
- Every brick in the dossier talks through process invocations, Git and the registry; none calls
  another. (b) keeps that rule. (a) would make knock the first brick that calls another.
- The orchestrator's current seam (`derive`, which writes a policy naming only the admitted tags) is
  replaced by "apply a filtered plan" without touching anything else in it.
- (a) remains reachable: an in-process gate is `--plan-out`, evaluate, `--apply-plan` in one
  command. Add it when a second orchestrator wants it; the matching logic below does not change.

## Decision 2: the plan format

```json
{
  "apiVersion": "knock.io/v1alpha1",
  "kind": "ReconcilePlan",
  "operations": [
    {
      "policy": "redis",
      "kind": "update",
      "destination": "harbor.corp/hub/redis",
      "tag": "7.2.5-hardened",
      "source": "docker.io/library/redis",
      "sourceTag": "7.2.5",
      "sourceDigest": "sha256:…"
    }
  ]
}
```

- **`kind`**: `import` (the tag is absent from the destination), `update` (the upstream digest moved
  and settled past the stability window), `rebuild` (the variant's transforms changed; the upstream
  digest may be unchanged). knock's report still calls the last two `updated`; the plan
  distinguishes them because an evaluator may want to treat them differently.
- **What to evaluate** is `{source}@{sourceDigest}`, never the tag.
- **The filtered plan is the same document with the refused entries removed.** There is no verdict
  field: absence is refusal. An orchestrator that wants to record why keeps that in its own journal
  (D-22), where it belongs.
- Deletions, retention marks, aliases and coverage backfills are not in the plan. None of them
  places a digest that was not already placed.
- The schema is derived from the Pydantic model (`reconcile_plan_json_schema()`) and published with
  the other schemas. Extra fields are refused, so a typo in a hand-edited plan fails loudly.

## Decision 3: how `--apply-plan` matches

`--apply-plan` recomputes the diff from live state, exactly as `reconcile` does. Each import,
update or rebuild is applied only if the file holds an entry with the same **(policy, destination,
tag, kind, sourceDigest)**. Otherwise it is **withheld**: not applied, reported with kind
`withheld`, and the destination tag is left as it is.

- **Drift fails closed.** If upstream re-pushed the tag after the plan was written, the live source
  digest differs from the approved one, and the operation is withheld until the next round judges
  the new digest. knock already copies and rebuilds from `{source}@{digest}`, so what is placed is
  byte-for-byte what was approved.
- **A stale entry does nothing.** An approved entry that no longer matches a live operation (the tag
  was placed meanwhile, the policy changed) is ignored.
- **Nothing already placed is touched by a refusal.** A withheld update leaves the old digest in
  service. A withheld import is not placed. The selection does not shrink, so nothing is purged: the
  derived policy's purge-on-omission edge disappears. An alias whose target is a withheld import is
  not moved, since its target does not exist in the destination; it keeps pointing where it did.
- Deletions, marks and backfills run as in `reconcile`.

## Decision 4: under the gate, `admit` is per operation

With `--apply-plan`, `admit: true` signs an image only when an approved operation placed it. The
attestation backfill on a kept digest attests it but does not sign it: that digest was not judged
in this round. So under the gate, a signature means "this exact digest was approved", which is what
ADR 0050's Decision 1 names as the target (option D).

Plain `reconcile` keeps 0.10.0's meaning (a policy-level assertion). Changing it would break the
orchestrator that uses it today. Once that orchestrator runs through the gate, making `admit: true`
require `--apply-plan` is a one-line follow-up and a separate decision.

## Limits

- **A rebuild is judged on its source, not its output.** The evaluator sees `{source}@{digest}`
  before the build; the rebuilt image only exists once built, and knock pushes it straight to the
  destination. Judging the output needs a closed transit to build into (D-32). That is out of scope,
  and the plan's `rebuild` kind is where it will attach.
- **Two passes, one state.** The plan is only as good as the policy directory both passes read.
  Running `--apply-plan` against a different policy set withholds everything the plan does not name,
  which fails closed.
- **`--plan-out` is a dry run.** It mutates nothing, including coverage backfills, which the next
  `--apply-plan` performs.

## Non-goals

- Calling an evaluator from knock (form a).
- Gating git-sourced placements.
- Digest pinning in the selection (a sibling change). The two compose: a pinned tag produces no
  `update`, so its plan entries are imports and rebuilds only.
