## Why

knock selects by tag name and resolves tag → digest only when it plans the copy. An orchestrator
that evaluates each candidate **by digest** and then hands knock a derived policy naming the admitted
tags (`tags: {includeRegex: "^$", names: [...]}`, with `spec.admit: true` since ADR 0050) leaves a
window: if upstream republishes a tag between the evaluation and knock's run, knock copies — and,
under `admit`, signs — a digest nobody judged. A signature is never removed (ADR 0050), so comparing
the placed digest afterwards is too late. `DEFAULT_GRACE` (7 days) delays an *update* but not a
first *import*, and it does not close the window for updates either.

The policy has no way to say which digest was admitted. This change adds one.

## What Changes

- **`TagSelection.pins: dict[str, str]`** — `{tag: digest}`, default `{}`. Each digest must be a
  `sha256:` or `sha512:` digest; otherwise the policy is rejected. A pin constrains a tag and does
  not select it: `names` / `includeRegex` still decide what is selected, and a pin on a tag that is
  not selected has no effect.
- **A pinned tag whose upstream digest differs from its pin is withheld for the run.** It is not
  imported, updated, re-signed or given a backfilled SBOM. It stays in the desired set, so what is
  already placed under that tag is not deleted, marked or re-pointed. An alias that would target
  the tag is not re-pointed in that run.
- **A pinned tag whose upstream digest matches its pin skips the stability window.** The pin is the
  judgement the window stands in for. Without this, the tag could be kept on an older, unjudged
  base for up to 7 days — and under `admit`, the signature backfill would sign that older digest.
- **A new, countable report outcome: `pin_mismatch`.** It is an `OperationKind` and a `Counts`
  field at every level of the `RunReport`, and it appears in the text recap. The operation carries
  the observed upstream digest (`digest`) and the expected one (`pinned_digest`). It is not an
  error: status and exit code do not change. The orchestrator reads the count and decides.
- **Unpinned tags behave exactly as today.**

## Schema choice

A separate `pins` map instead of `names: [{name, digest}]`:

- **It is additive.** `names` keeps its `list[str]` type, so existing policies, the published JSON
  Schema and every consumer that reads `names` stay valid. A union item type would break all three.
- **It covers regex selection too.** A pin applies to any selected tag, not just explicit names.
- **It merges like the rest of `tags`.** `defaults.tags` → import is a shallow merge, one key at a
  time, so `pins` is inherited or replaced as a whole, like `names`.
- **The orchestrator's derivation stays one line:** `names` = admitted tags, `pins` = the digests it
  evaluated.

## How this prepares D-30 (the gate between plan and apply)

D-30 (oci-supply-chain-spec, proposed) puts the gate inside knock, between the plan and the apply:
*a refusal removes the operation from the plan without touching what is already placed.* This
change builds that seam for the one refusal that needs no evaluator — "upstream no longer serves
the evaluated digest" (D-24's V-8 case):

- `VariantReconcile.pin_mismatch` is the first **withheld** plan entry. It is not an import, update
  or deletion. It keeps the tag in the desired set, and the apply stage gives it its own report
  outcome. D-30's refusals need the same three properties.
- Pins make the plan's input a list of `(tag, digest)` pairs rather than tag names. A written plan
  that an external evaluator filters (D-30's second form) needs the same pairs. The follow-up
  refusal kind can reuse this path instead of adding one.
- The limit is D-30's too: a pin judges the **source** digest. A rebuild's output digest exists only
  after the build, and it is judged at the transit (D-32), not here.

## Impact

- Domain: `mirror_policy.TagSelection` (the field), `expand.VariantPlan` (carries the pins),
  `reconcile.reconcile_variant` (the gate and skipping the stability window).
- Ports: `reporter.OperationKind` / `Counts` gain `pin_mismatch`.
- Use cases: `reconcile_registry` (emits the outcome), `report` (counts and schema).
- CLI: `render` (text recap).
- Docs: `docs/reference/` regenerated; `docs/examples/admission/admitted-redis.yml` pins its tag;
  ADR 0052.
