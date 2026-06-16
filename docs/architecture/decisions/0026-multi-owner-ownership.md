# 26. Multi-owner ownership: io.houba.owners replaces io.houba.owner.team

Date: 2026-06-16

## Status

Accepted

## Context

The provenance stamp carried ownership as a single free-text string,
`io.houba.owner.team`, sourced from `metadata.labels["team"]`. An image is
often co-owned, and ownership is better declared per import than per policy.
The full design is in
[the spec](../../superpowers/specs/2026-06-16-multi-owner-ownership-design.md).

## Decision

- Owners are declared as a list on `Defaults` and `ImportProfile` (`owners:`),
  inherited then overridden (wholesale) per import — consistent with the rest
  of the cascade. Variants inherit their import.
- An owner is a Backstage entity-ref string (`[kind:][namespace/]name`),
  validated by shape only — no catalog lookup. Forward-compatible with a future
  Backstage catalog integration at zero migration cost.
- Clean break of the public contract: `io.houba.owner.team` is removed and
  replaced by `io.houba.owners` (comma-joined, like `transform.steps`). No
  dual-write. `metadata.labels["team"]` is no longer an ownership source.
- `owners` stays optional; `io.houba.owners` is omitted when none resolve.
  Mandatory ownership (enforcement) is out of scope.

## Consequences

- Existing consumers of `io.houba.owner.team` must migrate to `io.houba.owners`
  and split on commas. The reference consumer `scripts/blast-radius.sh` is
  migrated in the same change (`BLAST_TEAM` → `BLAST_OWNER`, membership filter).
- No C4 change: Backstage is a future integration, not wired now.
