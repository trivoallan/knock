## Context

knock produces facts about the digests it places: the stamp, the SBOM referrer, and signed
attestations. It has never produced the one fact most enforcers check first, which is a signature
on the image itself. Admission (deciding which versions may enter) is decided **outside** knock
today. An orchestrator evaluates candidate versions and derives a `MirrorPolicy` that names only the
admitted tags. knock then places whatever that policy selects. A proposed next step would move the
gate into knock, between the plan and the apply.

This change needs to answer one question first: **how does knock know that an image is admitted?**

## Decision 1: the admission contract is an explicit, opt-in `spec.admit` flag

### Options considered

**A. Admitted by construction.** Every image knock places from a policy is admitted, so knock signs
everything it places. This needs no schema change, and it matches the current setup, where the
derived policy already names only admitted tags.

**B. An explicit per-policy flag, `spec.admit: true`, defaulting to `false`.** The author of the
policy asserts that everything this policy places is admitted. When admission is derived by an
orchestrator, the orchestrator writes the flag on the policy it derives.

**C. A per-import flag** (on `Defaults` / `ImportProfile`, like `owners`). This is finer-grained
than B.

**D. A per-digest verdict** that knock reads (a signed verdict attestation) or produces (the gate
moves into knock).

### Choice: B

- **Signing cannot be undone, so the default has to be the mistake you can recover from.** A
  signature on a version in service is never withdrawn (Decision 3). With option A, or with B
  defaulting to `true`, an author who forgets the flag on a transit or quarantine policy signs
  versions that were never admitted, and those signatures can never be removed. With B defaulting
  to `false`, the same forgetfulness leaves an admitted version unsigned. That is visible
  (`verify --require image-signature` fails, and so does the registry's content-trust check) and
  fixable (set the flag, and backfill signs it).
- **A holds only while placing and admitting are the same act.** They stop being the same the
  moment knock places anything before a verdict, such as a transit project scanned before
  promotion, or a gate inside knock that needs the image built before it can judge it. Once that
  happens, A is wrong, and wrong in the direction that cannot be undone.
- **C has no caller yet.** The orchestrator derives one policy per admitted set, so a policy-level
  flag is enough. Add per-import scope when a policy mixes admitted and non-admitted imports.
- **D is the target, not the first step.** D is the gate itself. It lands with the gate, and when
  it does, the flag becomes the *output* of the verdict for each operation rather than a policy
  assertion. The rest of this design survives that change: the signing primitive, the ordering
  after the attestations, the "never removed" rule, and the verify requirement.

### Tradeoff we accept

`admit: true` is a **policy-level assertion, not a per-digest verdict.** Two of the four
reconcile operations can place a digest that no verdict has seen:

- an **update**: the upstream tag moved, and knock re-imports after the 7-day stability window;
- a **rebuild**: the transforms changed, so the output digest is new.

Under `admit: true`, both get signed. The flag does not close that gap; only a per-operation gate
does. The contract is honest about this: the signature means *"placed by a policy whose author
asserted admission"*, and no more. An orchestrator that needs a per-digest guarantee should either
pin the admitted tags so updates are rare, or wait for the gate.

## Decision 2: sign last, with the attestation signer

knock signs the image after the stamp, the SBOM and the provenance attestation have all succeeded,
and it signs the **stamped output digest** (the stamp itself changes the digest). The signing step
sits inside the same `try` block as the attestations. If an earlier step fails, the operation fails
and the image stays unsigned. An admitted image therefore always carries its attestations.

knock uses the same `KNOCK_ATTEST_*` signer (`keyless` / `kms` / `key`), the same generated
signing-config, and the same `tls_verify` handling. There is no second signer and no new setting.

knock signs the index digest (a multi-arch index is signed as a whole). It does not sign each
platform manifest separately (`cosign sign --recursive`). Add `--recursive` if an enforcer is
found that checks per-platform digests.

## Decision 3: a signature is never removed from a version in service

knock never issues a delete against an image signature:

- `gc` collects only `SCAN_RESULT_ARTIFACT_TYPE` referrers;
- `purge` deletes a tag and its `PENDING_DELETION_ARTIFACT_TYPE` mark;
- reconcile deletes a tag that has left the selection, and its own pending marks;
- setting `admit: true` back to `false` stops new signatures and removes nothing.

A pull that worked keeps working. A version leaves service only through the existing deletion
pipeline (the selection or retention, then the usage oracle, then purge). No revocation path is
added. Revoking an admitted version is a separate decision that belongs to the enforcer's policy
(for example, a Kyverno exclusion), not to deleting the signature.

## Decision 4: `verify --require image-signature` checks the claim type, not presence

We checked this on 2026-09-19 against cosign v3.1.1 and a local `registry:2`:

1. `cosign sign` and `cosign attest` both store an OCI referrer with the **same** `artifactType`,
   `application/vnd.dev.sigstore.bundle.v0.3+json`. A referrer-presence check cannot tell a
   signature from an attestation.
2. **Plain `cosign verify` accepts an image that carries only an attestation**, and exits 0. The
   verified claim's `critical.type` is the attestation's predicate type, whereas a real image
   signature has `critical.type == "https://sigstore.dev/cosign/sign/v1"`.

So every image knock has ever attested already passes a bare `cosign verify`. `image-signature`
therefore runs `cosign verify` and passes **only** when at least one verified claim has
`critical.type == "https://sigstore.dev/cosign/sign/v1"`. Any other outcome is exit 1 (the gate
fails closed): cosign exits non-zero, no claim has that type, or the output cannot be parsed. Exit 2
is reserved for "cosign could not run", as with `scan-pass`.

**Consequence for enforcers outside knock.** An admission check that only asks "does cosign verify
this image?" treats knock's attestations as image signatures, and so treats every placed image as
admitted. That undoes the separation between signing and attesting. Enforcers must check the claim
type (Kyverno `verifyImages` with a signature `type`, or `knock verify --require image-signature`),
or check that the signature was made by a key or identity that is used *only* for admission. Using a
separate key for admission is the stronger form, and adding it later would be a configuration
change (a second signer), not a design change. Whether Harbor's "only signed images" rule tells the
two bundles apart is **not verified**.

The same ambiguity affects `audit`'s `signed` column and reconcile's `attested` coverage probe,
because both count sigstore-bundle referrers. Neither can be wrong about a knock-placed image that
is `admit: true`, since knock always attests before it signs. Both could over-report on an image
signed by a third party without a knock attestation. That problem predates this change and is noted
here rather than fixed.

## Non-goals

- Signing skill artifacts (git sources). `admit` is refused on them.
- Backfilling signatures onto images that are already attested but unsigned. Coverage cannot be
  read from the referrer's `artifactType` (Decision 4). It would take one `cosign verify` per
  existing tag on every reconcile. Add it when a policy flips to `admit: true` over a large existing
  fleet. Until then, `verify --require image-signature` finds the gap.
- Refusing to place anything without a signer. That is a broader rule that applies to attestations
  too, and it is tracked separately. This change refuses only `admit: true` without a signer.
