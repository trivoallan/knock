## Context

See `proposal.md` — Why. The relevant current state:

- `AttestorPort.sign(subject_ref)` and `verify_signature(subject_ref)` exist and take a bare OCI
  ref. Nothing in the port, the adapter or `cosign sign` is image-specific — `cosign` signs a
  manifest digest, and a skill artifact is a manifest.
- `attestor.sign` has exactly one call site: `reconcile_registry._attest_and_sign`, guarded by
  `sign and plan.policy.spec.admit`.
- `GitPlanner` is constructed in `reconcile.py` with `registry`, `source`, `archiver`, `roster`,
  `now`, `label_prefix`, `dry_run_tags`, `work_dir`. The driver already holds an `attestor` — it
  passes it to `RegistryPlanner` two lines above.
- `GitPlanner._apply_one` places the revision via `intake_skill`, which returns
  `IntakeResult.manifest_digest`, then moves the alias with a `registry.copy` of the revision tag.
- `MirrorPolicy` refuses `admit` on a git source in `_admit_needs_registry_source`.

The constraint that shapes everything below: the git path's convergence check is a conjunction
(revision placed AND alias designates it), and `_apply_one` has three distinct arrivals — place,
repoint-only, and fully converged. Signing has to be correct in all three, and cheap in the third,
which is the steady state.

## Goals / Non-Goals

**Goals:**

- One signature per admitted digest, placed before the alias points at it.
- Idempotence without a per-run signature verification: the steady-state run must not pay a cosign
  invocation per artifact.
- No new port, no new adapter, no new domain module.

**Non-Goals:**

- Provenance attestation on the git path. `build_git_stamp_annotations` already records the same
  facts as annotations; turning them into a signed in-toto Statement needs a new domain Statement
  builder and a new predicate type, and it is not what an admission controller reads.
- SBOM on the git path. syft over a source tree answers a different question than syft over an
  image, and a near-empty SPDX document attached as a referrer would read as coverage that is not
  there. Better absent than misleading.
- Any change to `knock verify`. It is already ref-generic (`verify.py` calls
  `registry.get_annotations` then `attestor.verify_signature` on whatever ref it was given) — the
  spec requirement about the gate is a statement that it already works, to be covered by a test,
  not a change.

## Decisions

### Reuse `spec.admit` rather than add a git-specific flag

`admit` means "everything this policy places is admitted". That sentence is true of a skill. A
second field (`sign_artifacts`, say) would mean the same thing with a different name and would let
the two drift. Removing the validator is the whole schema change.

*Alternative considered:* keep the validator and add the flag on `GitSource` itself. Rejected —
`admit` is a property of the policy's posture, not of where its bytes come from, and the field
already sits on `Spec` for that reason.

### Sign before the alias moves, not after

`_apply_one` places the revision tag, then `registry.copy`s it onto the ref name. Whoever installs
by ref name resolves through the alias. If the signature lands after the copy, there is a window
where the alias designates an unsigned digest and an enforcing admission controller rejects a
policy-declared skill. Signing first closes it, and costs nothing: the revision tag is immutable
and nobody follows it before the alias exists.

This inverts the registry path's "admission is the last act", and deliberately. There, the last act
is last because attestations must precede the signature. Here there are no attestations, and the
thing that must precede the signature is nothing at all — while the thing that must *follow* it is
the alias.

### Idempotence by referrer listing, not by `verify_signature`

On a converged artifact the question is "is this digest already signed". Two ways to answer:

1. `attestor.verify_signature(subject)` — one cosign invocation per artifact per run, and it
   verifies rather than merely detects.
2. `registry.list_referrers(subject, COSIGN_ATTESTATION_ARTIFACT_TYPE)` — one registry read,
   already the mechanism `reconcile_registry` uses for its attestation backfill.

Take (2), and it is *more* precise here than on the image path. There, a cosign bundle referrer is
ambiguous between an attestation and a signature (cosign v3 stores both as the same bundle type),
which is why that path has to say "a present bundle ⇒ knock already did its thing". On the git path
knock attaches no attestations at all, so a cosign bundle on a knock-placed skill means exactly one
thing: it was signed.

*Trade-off:* a bundle put there by a third party would suppress knock's signature. The upgrade path
is the one `domain/attestation.py` already names — attach a knock-owned marker referrer and match
that instead. Not worth building until someone else writes to these digests.

### Refuse `admit` without a signer during `plan`, per planner

`RegistryPlanner` refuses at plan time so nothing is placed unsigned. `GitPlanner.plan` gets the
same guard, on its own batch: `if any(p.spec.admit for p in policies) and self.attestor is None:
raise ConfigError(...)`. Keeping it per-planner rather than lifting it into the driver means the
check runs where the attestor is actually needed, and a run with only registry policies is
unaffected by a missing git attestor and vice versa.

### `attestor` is `AttestorPort | None` on `GitPlanner`

Matching `RegistryPlanner`. `None` is the legitimate state when no signer is configured, which is
the default; the plan guard is what turns `None` into an error, and only when a policy asks for
admission.

### Dry-run places nothing, so it signs nothing

`--dry-run-tags` returns planned operations without fetching or pushing. There is no digest to
sign. The dry-run report says `imported` / `aliased` and stays silent about the signature — a
planned signature on a digest that does not exist yet would be a fact about nothing.

## Risks / Trade-offs

- **An admitted skill carries a signature and no attestation, unlike an admitted image.** →
  Accepted and explicit. `knock verify --require image-signature` passes on it; `--require
  scan-pass` and `--require sbom` do not, and correctly so — those facts are genuinely absent. The
  stamp still carries the provenance, unsigned.
- **A third-party cosign bundle on a knock-placed digest suppresses signing.** → Named above;
  upgrade path is a knock-owned marker referrer.
- **The backfill costs one referrer listing per converged artifact per run, on `admit: true`
  policies only.** → It is a registry read on a digest the planner has already resolved, and it is
  paid only when admission is on. `admit: false` policies — the default — pay nothing.
- **This change retracts a requirement `sign-image-at-admission` published** ("Git source refuses
  admit"). → It was archived on 2026-09-20, so that clause is now live in
  `openspec/specs/image-signature/spec.md` and contradicts the shipped code. A delta on the new
  `artifact-signature` capability cannot retract it; only a delta on `image-signature` can, and
  this change carries one. Note the correction to the original plan here: archiving 0050's change
  first does not avoid the conflict, it *materialises* it — which is what made the delta necessary
  rather than optional.
- **The retraction is spelled REMOVED + ADDED, not MODIFIED.** `openspec validate` refuses a
  MODIFIED block that drops a scenario the current spec still has, and dropping "Git source refuses
  admit" is precisely the point. So the requirement is removed with a reason and re-stated under a
  widened name.

## Migration Plan

No data migration and no breaking change: `admit` defaults to `false`, so an existing git policy
behaves exactly as before. A policy that previously failed to parse with `admit: true` on a git
source now parses — strictly a widening.

Rollback is the field: set `admit: false`. Signatures already placed stay, by design.

## Open Questions

None.
