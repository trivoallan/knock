# 20. Propagate `.revision` from the source image; omit when undeclared

Date: 2026-06-15

## Status

Accepted

## Context

`org.opencontainers.image.revision` is an OCI-standard annotation whose semantics are the
**SCM commit hash of the software packaged in the image**, not a registry artifact identifier.
houba was previously stamping it with the source manifest digest (the same value already carried
by `org.opencontainers.image.base.digest`). This was wrong on two counts:

1. **OCI semantics.** The OCI Image Spec defines `.revision` as the source-control revision of the
   packaged software (e.g. a Git commit SHA). A digest is an artifact address, not a source
   revision; conflating the two misleads any tool that reads `.revision` to find the upstream
   commit.

2. **Redundancy.** `base.digest` already records the source manifest digest as the idempotency key
   and blast-radius handle. A second copy of the same value under `.revision` adds noise without
   information — and "the label is the product" means the stamp must be trustworthy before real
   artifacts depend on it.

## Decision

`org.opencontainers.image.revision` is **propagated from the source image's own declaration**:
houba reads the source manifest's OCI annotation first (annotation wins); if absent, falls back
to the equivalent config label. When the source declares no revision at all, `.revision` is
**omitted** from the stamp — houba does not fabricate a value from the digest, a tag, or anything
else.

Lookup priority (highest wins):
1. Source manifest annotation `org.opencontainers.image.revision`
2. Source image config label `org.opencontainers.image.revision`
3. Absent → key omitted entirely

No new port, adapter, or actor was introduced. The change extended the existing `ImageInfo`
data model on the `RegistryPort` to carry the propagated revision field; `domain/stamp.py`
consumes it. **C4 model: unchanged.**

## Consequences

- The stamp becomes honest: `.revision` either reflects the upstream maintainer's declared Git
  commit (useful to any scanner or SBOM tool that traces back to source) or is absent (the
  absence is itself informative — the source image has no declared revision).
- `base.digest` is no longer shadowed by a redundant `.revision == base.digest`. Both keys now
  carry distinct semantics, consistent with the OCI spec.
- Downstream tools relying on the old `.revision == base.digest` equivalence will see a
  different value (the actual upstream commit, or key absence). This is a deliberate breaking
  change: the old value was meaningless by the spec.
- Images whose upstream maintainers do publish `.revision` (e.g. official images with full OCI
  annotation sets) will carry that commit hash through houba's stamp, making source traceability
  free.

Full design spec: [2026-06-15-revision-semantics-design.md](../../superpowers/specs/2026-06-15-revision-semantics-design.md)
