# Proposal

## Why

A rebuild is pushed straight to its destination, so nothing can judge the image knock produced
before consumers can pull it. The gate (`reconcile-gate`) lets an evaluator refuse an operation on
its **source** digest only. A real run on 2026-10-10 showed why that is not enough: of three
rebuilds whose source called for a repair, one came out compliant, one still failed the same
rules, and one was pushed with nothing repaired at all. ADR 0051 names this limit and ADR 0054
defers turning the repair on until it is closed.

## What Changes

- `knock reconcile --apply-plan` accepts a **staging registry**. With it, every operation that
  builds an image pushes, stamps and attests that image in the staging registry instead of the
  destination, and knock writes a **staged rebuilds** file listing each one with its digest.
  Operations on the copy path, deletions, retention marks and backfills run as they do today.
- A new verb, `knock promote`, reads a filtered copy of that file and places each remaining entry:
  it copies the staged digest and its referrers to the destination, writes the tag, signs when the
  policy admits, and moves the aliases. An entry removed from the file is never placed: absence is
  refusal, as with the plan.
- The digest that is promoted is the digest that was staged. Promotion refuses an entry whose
  staged digest is gone or different, and refuses an entry that names a destination its policy
  does not declare.
- Copying an image can now carry its referrers (SBOM, attestations) along.
- Without the staging option, nothing changes: no existing run, plan file or policy is affected.

Not in this change: evaluating a staged image (knock still calls no evaluator), cleaning the
staging registry, and any policy field that chooses when a rebuild or a repair is triggered.

## Capabilities

### New Capabilities

- `staged-rebuild`: holding rebuilt images in a staging registry during `reconcile --apply-plan`,
  the staged rebuilds file, and promoting approved entries to their destination with `knock promote`.

### Modified Capabilities

- `image-signature`: verification with a file key uses its public half. Found while verifying this
  change's premise: with `signer: key` and a key file, verification returned nothing on any
  registry. The promotion's arrival check depends on it.

`reconcile-gate` keeps its requirements: a staged image is not a placement, so the rule "only
approved placements are signed" already covers it.

## Impact

- **CLI**: two options on `reconcile` (`--stage-to`, `--staged-out`), one new verb (`promote`).
  The generated CLI reference changes.
- **Domain**: a `StagedRebuilds` document with a published JSON Schema, next to `ReconcilePlan`.
- **Ports / adapters**: `RegistryPort.copy` gains a way to carry referrers; the regctl adapter and
  its fake-bin follow. `AttestorPort` gains `has_attestation`, a verification that does not read
  the predicate. `Counts` gains a `staged` count.
- **Use cases**: the registry reconcile path routes building operations to the staging registry;
  a new promotion use case.
- **Docs**: ADR 0055, the gate example gains the two-phase walkthrough, `TODOS.md` loses its
  two-phase placement entry. The C4 model gains no element: a staging registry is one more OCI
  registry from the roster.
- **Operators**: a staging registry must be reachable by knock and by the BuildKit daemon, and
  listed in `KNOCK_REGISTRIES`. An orchestrator that wants the second gate runs three steps
  instead of one (apply with staging, evaluate, promote).
- **Dependency**: independent of the open `upgradePackages` work. It is the precondition ADR 0054
  sets for turning that step on.
