# 55. Stage rebuilt images, promote them after a verdict

Date: 2026-10-10

## Status

Accepted.

Builds on [51. The gate between reconcile's plan and its application](0051-gate-between-plan-and-apply.md):
closes the limit its consequences name (a rebuild is judged on its source digest; judging the
rebuilt output needs a closed transit). Uses the signature of
[50. knock signs the image at admission](0050-knock-signs-the-image-at-admission.md) as the last
act of a promotion.

## Context

A rebuild is one gesture: the build pushes to the destination, then knock stamps, attaches the
SBOM, attests and signs. Nothing can judge what knock produced before consumers can pull it. The
gate lets an evaluator refuse an operation on its source digest only, and a source verdict says
little about a rebuilt image: in a real run of a repair step, of three rebuilds whose source
called for a repair, one came out compliant, one still failed the same rules, and one was pushed
with nothing repaired.

## Decision

- **A staging registry.** `reconcile --apply-plan FILE --stage-to NAME --staged-out FILE` pushes
  every operation that **builds** an image to the registry `NAME` of the roster instead of its
  destination, at the destination's path re-rooted under the staging host. The image is stamped,
  carries its SBOM and its signed attestations there, and is **not signed as admitted**. Copies,
  deletions, retention marks and backfills run as before: a copied image is byte-identical to the
  source the gate judged.
- **A second file seam.** The run writes a `StagedRebuilds` document: one entry per held image,
  with its destination, its source, the staged repository and digest, and the aliases reconcile
  resolved onto that tag. Its JSON Schema is derived from the model and published. An
  orchestrator evaluates `{staged}@{stagedDigest}` and removes the entries it refuses. Absence is
  refusal, as with the plan.
- **`knock promote DIR --staged FILE`** places the remaining entries. The file is edited outside
  knock and this verb writes to the destination and signs, so the file says *whether*, never
  *where* or *what*. For each entry promote requires that: the policy declares the destination;
  the staged repository is that destination re-rooted under a roster registry; the staged
  reference still resolves to the evaluated digest; the image's stamp names the entry's policy,
  import, variant and source digest; the import selects the tag and lets it carry the recorded
  aliases. It then copies **by digest with referrers**, verifies at the destination that the SBOM
  and, when a signer is configured, a signed transform attestation arrived, and **only then
  writes the tag**. It signs when the policy admits, and writes the recorded aliases.
- **One alias rule.** reconcile resolves aliases from the tags it selected in the source and never
  retargets to a lower tag. promote replays what reconcile recorded and computes nothing. During a
  staged run an alias never moves onto a held tag.
- **Two adapter facts this rests on.** A plain `regctl image copy` brings the manifest and no
  referrer; `--referrers` brings them, and the digest is unchanged. Verification of the transform
  attestation needs a check that does not decode the predicate (`AttestorPort.has_attestation`),
  and, with a file key, the key's public half.

## Consequences

- A rebuilt image can be judged by digest before any consumer can pull it from its destination,
  and the digest that is promoted is the digest that was judged, with its evidence.
- An entry that fails does not stop the others; the command exits non-zero. Promoting the same
  file twice changes nothing.
- A staged image that is never promoted leaves no trace in the destination: the next pass plans
  the same operation again. What stops re-judging is the orchestrator's record, not knock.
- **The staging registry must not be one consumers pull from.** knock refuses a staging registry
  that is also a destination of the policy; it cannot know more. An ephemeral registry that lives
  for the run is the simplest form.
- **Sizing.** The staging registry receives every layer of every rebuilt image, base layers
  included, and promotion then sends the destination the layers it lacks. An ephemeral staging
  volume must hold the unique blobs of one pass. A change that rebuilds a wide selection at once
  fills it, and the builds then fail loudly.
- An ephemeral registry that dies between the two commands fails those entries; the next pass
  rebuilds them, possibly to another digest, which is judged again.
- knock never deletes from the staging registry and knows no retention there.
- An orchestrator that wants the second gate runs three steps instead of one: apply with staging,
  evaluate, promote.
- `RegistryPort.copy` and `AttestorPort` each gain one capability; `Counts` gains `staged`. No new
  port, adapter, external system or C4 element: a staging registry is one more OCI registry of
  the roster, and the reference deployment does not deploy one.
- Verified with regctl v0.11.6, cosign v3.1.3, BuildKit v0.30.0 rootless and `registry:2` on both
  sides: four rebuilds staged with their SBOM and attestations and unsigned; one promoted with
  its alias and signed, digest identical, four referrers at the destination; one deleted from
  staging failed without stopping the other; a second promotion skipped; the unpromoted ones were
  planned again.

See the [design](https://github.com/trivoallan/knock/blob/main/openspec/changes/stage-and-promote-rebuilds/design.md).
