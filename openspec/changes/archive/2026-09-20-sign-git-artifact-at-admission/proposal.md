## Why

`sign-image-at-admission` gave knock an image signature at admission, but only on the registry
path. The git path — the one that places agent skills (ADR 0048) — was explicitly excluded:
`_admit_needs_registry_source` refuses `admit: true` on a git source, and `GitPlanner` is not even
constructed with an attestor. A skill knock places today is stamped and nothing else. It carries no
signature, so `knock verify --require image-signature` on a placed skill is a fail-closed exit 1
forever, and an admission controller that enforces signatures cannot let a knock-placed skill
through at all.

That is the gap: knock cannot sign a standalone artifact. The decision verb and the enforcement
story stop at the registry path, while the artifact class knock most recently added is the one an
org is least likely to have any other provenance for.

## What Changes

- **`spec.admit` is accepted on a git source.** The `_admit_needs_registry_source` validator is
  removed. The field keeps its meaning and its default (`false`): everything this policy places is
  admitted, so knock signs it.
- **knock signs the placed artifact** (`cosign sign`) on the git path when the policy is
  `admit: true`. It signs the revision digest the intake returned, immediately after the artifact
  is placed and **before** the alias moves onto it, so a reader following the ref name never
  resolves to an unsigned digest.
- **Idempotent backfill on converged artifacts.** When an `admit: true` policy finds a revision
  already placed, knock lists the digest's referrers and signs it only when no cosign bundle is
  there. Turning `admit` on therefore signs an existing mirror on the next run, and a steady-state
  run signs nothing twice.
- **`admit: true` without a signer is refused** on the git path as it already is on the registry
  path — `ConfigError`, exit 3, at plan time, before anything is placed.
- **No attestation and no SBOM on the git path.** Signature only. The reasons, and the upgrade
  path, are in `design.md`.
- **A signature is still never removed.** Setting `admit` back to `false` stops new signatures and
  deletes none.

## Capabilities

### New Capabilities
- `artifact-signature`: admission signing of a standalone (non-image) OCI artifact placed from a
  git source — when knock signs it, what it signs, idempotence, and refusal without a signer.

### Modified Capabilities
- `image-signature`: the requirement "A policy declares admission explicitly" is removed and
  re-stated as "…, whatever its source", without the git-source refusal (a MODIFIED block cannot
  retract a scenario). `sign-image-at-admission` has since been archived, so that clause is now a live
  statement in `openspec/specs/image-signature/spec.md` and contradicts the shipped code — a new
  capability alone cannot retract it, only a delta on this one can.

## Impact

- Schema: remove `_admit_needs_registry_source` from `knock/domain/mirror_policy.py` and widen the
  `admit` field description. Regenerate `docs/reference/` with `make reference`.
- Ports: none. `AttestorPort.sign` / `verify_signature` already exist and are ref-generic.
- Adapters: none. `cosign sign` takes any OCI ref by digest.
- Use cases: `GitPlanner` gains an `attestor: AttestorPort | None` constructor field (wired in
  `reconcile.py`, which already holds one); `_apply_one` signs after placement; the plan phase
  refuses `admit` without a signer.
- Domain: none. `COSIGN_ATTESTATION_ARTIFACT_TYPE` is reused as the already-signed marker.
- Tests: a `sign` branch already exists in `tests/fake-bins/cosign`; `FakeAttestorPort` already
  journals `signed`.
- Docs: ADR amending ADR 0050 (which itself amended 0041), the skills how-to, and the skills
  example policy.
- C4: no new actor, no new external system, no new port/adapter pair. The Component view's
  GitPlanner gains an edge to the existing attestor.
