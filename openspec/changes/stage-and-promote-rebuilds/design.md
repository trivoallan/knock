# Design

## Context

See `proposal.md` for the motivation. What shapes the approach:

- The gate (ADR 0051) is a file seam: `reconcile --plan-out` writes a `ReconcilePlan`, an
  orchestrator removes refused entries, `reconcile --apply-plan` applies the rest. knock calls no
  evaluator and does not know why an entry is missing.
- A rebuild is one gesture today: the build pushes to the destination reference, then knock stamps
  the image (`regctl image mod`, which changes the digest), attaches SBOM referrers, attests, and
  signs when the policy admits. An alias is then moved to the highest placed tag.
- The stamp carries no location fact (ADR 0020), so a stamped digest is the same in any registry.
- `RegistryPort.copy` runs `regctl image copy` without options: referrers do not follow a copy.
- A destination names a registry from the `KNOCK_REGISTRIES` roster; the roster already carries
  host, TLS and credentials per registry.
- `docs/roadmap.md` lists two-phase placement as "design and ADR only". `TODOS.md` asks for the
  ADR first, then a Deployment view in the C4 model.

## Goals / Non-Goals

**Goals:**

- A rebuilt image can be judged by digest before any consumer can pull it from its destination.
- The second seam looks like the first: a file knock writes, an orchestrator filters, knock applies.
- knock remains the only writer of the destination.
- The staging location is configuration: an ephemeral registry today, a private project of the
  destination registry later, with no code change.

**Non-Goals:**

- Evaluating anything, or recording why an entry was removed.
- Deleting from the staging registry, or any retention there. Its owner disposes of it.
- Staging the copy path. A copied image is byte-identical to the source the first gate judged.
- Staging without the gate (`--stage-to` without `--apply-plan`).
- Git-sourced artifacts (skills): they are not rebuilt.
- Policy fields that choose when to rebuild or repair. That is a later change that builds on this one.

## Decisions

### 1. Stage in a registry named in the roster, at the same repository path

`--stage-to <name>` resolves through `KNOCK_REGISTRIES` like any destination. The staged reference
is `<staging host>/<destination project>/<destination repository>:<tag>`: the destination path,
re-rooted. No new configuration shape, credentials and TLS come for free, and two destinations of
one policy cannot collide.

*Rejected:* a dedicated `KNOCK_STAGING_*` setting (a second way to describe a registry); a flat
staging repository keyed by digest (unreadable when debugging, and tags are what `regis`-like
evaluators and humans address).

### 2. Everything that makes the digest happens in staging; admission happens at promotion

In staging: build, stamp, SBOM referrers, signed attestations. These define the artifact and the
evaluator may want to read them. Not in staging: the admission signature (`admit: true`) and the
aliases, which say "this is in service". `_attest` is called with `sign=False` when staging, and
promotion signs the destination reference after the copy.

This keeps `reconcile-gate`'s rule intact: a signature still means an approved placement.

### 3. `StagedRebuilds`, a sibling of `ReconcilePlan`

A frozen pydantic document in the existing `knock/domain/gate.py`, next to `ReconcilePlan`: the two
files are the two seams of the same gate and share conventions. `apiVersion`, `kind: StagedRebuilds`,
`entries`. An entry carries what the plan entry carries (policy, kind, destination, tag, source,
sourceTag, sourceDigest) plus `import`, `variant`, `staged` (repository), `stagedDigest` and
`aliases` (decision 7).
`extra="forbid"`, camelCase aliases, schema published under `docs/reference/schemas/` by
`make reference`, like the plan.

The evaluator addresses `{staged}@{stagedDigest}`. Filtering is deletion of entries, nothing else.

*Rejected:* extending `ReconcilePlan` with optional staged fields. The two files are written at
different moments by different runs; one document with two lifecycles would make "which fields are
trustworthy now" a reader's problem.

### 4. `promote` is a verb, not a third mode of `reconcile`

`knock promote <dir> --staged <file>`. It does not diff, select or plan: it places named digests.
Giving it its own verb keeps `reconcile`'s option matrix from growing a fourth exclusive mode and
gives the use case its own module (`knock/use_cases/promote.py`).

It takes `<dir>` because it needs each entry's policy: to check the destination is declared, to
read `admit`, and to compute aliases with the same domain function reconcile uses.

### 5. Promotion trusts the file for *whether*, never for *where* or *what*

The file is edited outside knock. Promotion therefore re-derives what it can:

- the destination must be one the named policy and import declare, else the entry fails;
- the staged repository must be that destination re-rooted under a roster registry (decision 1),
  else the entry fails: `promote` never pulls from a location the file invents;
- the staged reference must still resolve to `stagedDigest`, else the entry fails;
- the staged image's stamp (`get_annotations`) must name the entry's policy, import, variant and
  source digest, else the entry fails: `promote` places only what knock stamped for that entry;
- after the copy, the destination digest must equal `stagedDigest`, and its SBOM referrers and,
  when a signer is configured, its signed attestation (`AttestorPort.has_attestation`) must be
  found there, else the entry fails and the tag is not written.

`has_attestation` is a new port method. The real run of task 8.1 showed `AttestorPort.verify`
cannot serve here: it decodes scan predicates (`summary`, `attested_at`) and drops any other, so
it returned nothing for the transform attestation and promotion refused every entry. The check
failed closed, which is the behaviour wanted, and a fake that returned generic predicates had hidden
it from the unit tests. `has_attestation` asks cosign the same question and reads nothing from the
predicate.

A copy that exits 0 does not prove the evidence arrived: registries and tools differ in how they
store and discover referrers. Hence the order in decision 6: copy by digest, verify, then tag.

A failed entry is reported like any failed operation and does not stop the others (the existing
partial-failure convention). New leaf error: `StagedDigestMismatchError` under `AdapterError`,
next to `SourceRevisionMismatchError`.

### 6. Copy carries referrers through an explicit port option

`RegistryPort.copy(src, dst, *, referrers: bool = False)`; the regctl adapter adds `--referrers`
(and `--digest-tags` if task 1.1 shows the attestor stores anything under digest tags). Default
`False` keeps every existing call byte-identical. Promotion is two steps: copy
`{staged}@{stagedDigest}` to `{destination}@{stagedDigest}` with referrers, verify at the
destination (decision 5), then write the tag inside the destination repository, as an alias write
does today. Promoting twice is a no-op: the second run finds the tag at the staged digest.

**Verified on 2026-10-10** (task 1.1; regctl v0.11.6, cosign v3.1.3, `registry:2` on both sides,
BuildKit v0.30.0 rootless, `signer: key`): a plain copy by digest brings the manifest and **no**
referrer; `regctl image copy --referrers` brings all three (SPDX SBOM and the two sigstore bundles)
and the referrers fallback tag; `--digest-tags` is not needed. The digest is identical on both
sides. A digest-only destination (`repo@sha256:...`) is accepted and leaves no tag; the tag is then
written by a copy inside the destination repository. `knock verify --require stamp` and
`--require sbom` pass against the second registry, and `cosign verify-attestation` with the public
key passes there.

**Found while verifying, not caused by this change:** with `signer: key` and a key *file*,
`AttestorPort.verify` returns no predicate on any registry. The adapter passes `KNOCK_ATTEST_KEY_REF`
(the private key) to `cosign verify-attestation --key`, which cosign v3 refuses, and the adapter
maps that failure to an empty result. Verification works with a KMS URI or a public key. The
arrival check of decision 5 depends on `verify`, so this must be settled before task 6.1.

The original premise, kept for the record: that after such
a copy the SBOM referrers and the attestations are attached to the same digest in the target, and
that `knock verify` passes there. If it does not hold, promotion must re-attach and re-attest in
the destination and decision 2 changes.

### 7. Aliases: withheld during staging, computed at promotion

During a staged run, a staged tag absent from the destination is treated exactly like a withheld
import: the existing "alias must not move onto a withheld import" branch is reused. The aliases
that reconcile resolved onto a staged tag are recorded in that tag's entry. At promotion they are
written after the tag, and an alias the policy does not declare fails the entry.

`promote` computes no alias target. reconcile resolves aliases from the tags it selected in the
source and never retargets to a lower tag; a second rule based on the destination's tags would
diverge from it when the highest tag is refused.

*Rejected:* recomputing from destination tags (two rules); leaving aliases to the next pass (an
alias lags its promoted tag by one pass).

### 8. Reporting

`Counts` gains `staged`. A staged operation emits an `OperationEvent` of kind `staged` carrying the
staged digest; the summary line prints `staged=N`. `promote` reports each entry under its original
kind (`imported` / `updated`), so dashboards built on those counts keep meaning "placed".

### 9. Verify with the public half of a file key

`_verify_args` passes `KNOCK_ATTEST_KEY_REF` to `cosign verify --key`. For a KMS URI that is right.
For a private key file cosign v3 refuses it, and the adapter maps the failure to "nothing verified".
In `key` mode the adapter now reads the file: a public key is used as is; otherwise the public key
is derived with `cosign public-key --key <ref>` into the call's temporary directory and passed
instead. A derivation failure raises `CosignError`: a broken key is a fault, not an absence of
attestations.

*Rejected:* a second setting for the verification key. One reference already identifies the key
pair, and a verify-only deployment can point it at the public key.

## Risks / Trade-offs

- [Referrers do not survive the copy with the deployed registry or tool versions] → task 1.1 runs
  first and gates the design; the fallback is stated in decision 6.
- [The staging registry is reachable by consumers] → out of knock's hands; the ADR states that the
  staging registry must not be one consumers pull from, and the example uses an ephemeral one.
- [An ephemeral staging registry dies between apply and promote] → promotion fails those entries
  (digest gone), nothing is placed, and the next pass plans and rebuilds them again. The rebuilt
  digest may differ; it is judged again. Accepted.
- [A rebuild that is refused repeats on every pass] → same as a withheld operation today; the
  orchestrator's journal is what stops re-judging, not knock.
- [Staging stores and moves every rebuilt image once more] → the staging registry receives all
  layers of each rebuilt image, base layers included, then one registry-to-registry copy per tag
  sends to the destination the layers it lacks. An ephemeral staging volume must hold the unique
  blobs of one pass; a change that rebuilds a wide selection in one pass can fill it, and the builds
  then fail loudly. The ADR states the sizing rule.
- [The BuildKit daemon cannot reach or trust the staging registry] → it uses the roster entry's
  `tls_verify`, as for any destination; the example documents the requirement.
- [Roadmap discipline] → the roadmap reserves this item for "design and ADR only". This change
  includes the implementation: the ADR is written first (task group 2) and the roadmap line is
  updated in the same change.

## Migration Plan

Additive and off by default. No policy, plan file or existing invocation changes. An orchestrator
adopts it by adding `--stage-to` / `--staged-out` to its apply step and a `promote` step after its
own evaluation. Rollback: drop the two options and the step; the next pass places rebuilds directly.

## Open Questions

None left. `promote` takes no dry-run flag: it places named digests and plans nothing, so a dry
run would only re-read the file. `reconcile --dry-run` with `--stage-to` stages nothing and writes
an empty file.
