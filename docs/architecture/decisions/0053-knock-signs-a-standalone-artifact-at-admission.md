# 53. knock signs a standalone artifact at admission

Date: 2026-09-20

## Status

Proposed.

Amends [50. knock signs the image at admission](0050-knock-signs-the-image-at-admission.md): the
clause refusing `spec.admit` on a git source is superseded. Builds on
[48. Non-registry sources and the skill artifact class](0048-non-registry-sources-and-the-skill-artifact-class.md)
and [49. Reconciling git sources](0049-reconciling-git-sources.md).

## Context

ADR 0050 gave knock an image signature at admission and drew the line at the registry path:
"the flag is refused on a git source". The git path places agent skills, and it placed them
stamped and nothing else — no signature, no attestation.

That left the decision verb half-blind. `knock verify --require image-signature` on a placed skill
was a fail-closed exit 1 forever, and an admission controller enforcing signatures could not let a
knock-placed skill through at all. The artifact class knock most recently added is also the one an
org is least likely to have any other provenance for, so the gap fell exactly where the product
claim is weakest.

Nothing technical forced the line. `AttestorPort.sign` takes a bare OCI ref and `cosign sign` signs
a manifest digest; a skill artifact is a manifest. The refusal recorded an unbuilt path, not an
impossibility.

## Decision

- **`spec.admit` is accepted on a git source.** Same field, same meaning, same `false` default:
  everything this policy places is admitted. A separate flag would say the same thing under a
  second name and let the two drift. `admit` is a property of the policy's posture, not of where
  its bytes come from.
- **knock signs before the alias moves.** On the git path the signature lands on the placed
  revision's digest, and then the ref-name alias is copied onto it. This inverts 0050's "admission
  is the last act" deliberately: there, the signature comes last because the attestations must
  precede it; here there are no attestations, and what must *follow* the signature is the alias.
  Whoever installs by ref name resolves through it, so signing afterwards would leave a window in
  which the alias designates an unsigned digest.
- **Signature only — no attestation, no SBOM.** The stamp already records the same provenance facts
  as annotations, and an admission controller reads the signature, not a predicate. syft over a
  source tree answers a different question than syft over an image; a near-empty SPDX document
  attached as a referrer would read as coverage that is not there. Better absent than misleading.
- **Backfill by referrer listing.** A converged revision is signed only when its digest carries no
  cosign bundle, so turning `admit` on signs an existing mirror on the next run and a steady-state
  run signs nothing twice. On the image path a cosign bundle is ambiguous between an attestation
  and a signature; on the git path knock attaches no attestations, so here the marker means exactly
  one thing.
- **`admit: true` without a signer is refused at plan time** (`ConfigError`, exit 3), before any
  fetch — as it already is on the registry path.
- **A signature is still never removed.** Setting `admit` back to `false` stops new signatures and
  deletes none.

## Consequences

- An admitted skill carries a signature and no attestation, unlike an admitted image. `knock verify
  --require image-signature` passes on it; `--require sbom` and `--require scan-pass` do not, and
  correctly so — those facts are genuinely absent, not merely unplaced.
- A cosign bundle put on a knock-placed digest by a third party would suppress knock's signature.
  The upgrade path is the one [ADR 0015](0015-scan-attestation.md)'s successor already names: a
  knock-owned marker referrer matched instead of the bundle type.
- The backfill costs one referrer listing per converged artifact per run, on `admit: true` policies
  only. The default posture pays nothing.
- No new port, adapter, external system or C4 actor: `GitPlanner` gains an edge to the attestor the
  driver already holds.

Full change: [openspec/changes/sign-git-artifact-at-admission](../../../openspec/changes/sign-git-artifact-at-admission/proposal.md)
([design](../../../openspec/changes/sign-git-artifact-at-admission/design.md)).
