# Multi-owner ownership (`io.houba.owners`)

**Status:** designed (2026-06-16)
**Scope:** enrich the ownership half of the provenance stamp — from a single
free-text `team` to a list of owners declared per import, stamped as
`io.houba.owners`, and consumed by the reference blast-radius script.

## Problem

Today ownership is a single optional free-text string sourced from
`metadata.labels["team"]`, stamped as `io.houba.owner.team`, and rolled up by
`scripts/blast-radius.sh` to answer *"who do we page?"*. Two limits hurt at
incident time:

1. **One flat string can't model real ownership.** An image is often co-owned
   by more than one team. A single value forces a lossy choice.
2. **Ownership is declared too coarsely.** It lives at policy level
   (`metadata.labels`), but a policy with several imports may have different
   owners per import.

## Decisions

- **Owner shape: Backstage entity-reference string, validated by shape only.**
  An owner is a string following Backstage's `[<kind>:][<namespace>/]<name>`
  convention (e.g. `group:default/payments`, or short `payments`). houba
  validates the *form* with one permissive regex and **does not normalize** —
  the value is stamped exactly as written. This is forward-compatible with a
  future Backstage catalog integration (out of scope here) at zero migration
  cost, stays readable in YAML, and serializes trivially into the OCI
  annotation. No catalog lookup, no existence check.

- **Declared at `Defaults` + `ImportProfile`, override semantics.** A policy may
  set a default `owners` in `defaults:` that every import inherits, and override
  it per import. An import that declares `owners` **replaces** the inherited list
  (wholesale, like `destinations`/`platforms` — not a union). `Variant` is
  unchanged and inherits its import's ownership.

- **`owners` is optional.** When no owner resolves, `io.houba.owners` is omitted
  (same as `owner.team` today). Making ownership *mandatory* is enforcement,
  explicitly out of scope.

- **Clean break of the public contract.** `io.houba.owner.team` is **removed**,
  replaced by `io.houba.owners` (plural). The list serializes comma-joined
  (Backstage refs never contain commas), consistent with
  `io.houba.transform.steps`. No dual-write, no transitional alias — the
  reference consumer migrates in the same change. Recorded as an ADR.

- **Clean break of the source.** `metadata.labels["team"]` is **no longer**
  read as an ownership source. Owners come exclusively from the new `owners`
  field. `labels` stays a generic free-form `dict[str, str]` for other uses.

## Changes

### `domain/mirror_policy.py`
- Add `owners: list[str] | None = None` to `Defaults` and `ImportProfile`
  (camelCase YAML: `owners`).
- Validate each owner against the Backstage-ref regex; malformed → raise
  `PolicyValidationError`. An empty list is allowed (≡ no owner).

### `domain/policy_merge.py`
- `ResolvedImport` gains `owners: list[str] | None`.
- Resolve by wholesale override:
  `owners = imp.owners if imp.owners is not None else (d.owners if d else None)`.

### `domain/stamp.py` (contract break)
- Signature: `team: str | None` → `owners: list[str] | None`.
- Emit `{prefix}.owners = ",".join(owners)` when `owners` is non-empty; omit
  otherwise.
- Remove the `{prefix}.owner.team` branch.

### `use_cases/reconcile.py`
- Replace `team=(plan.policy.metadata.labels or {}).get("team")` with the
  resolved import's `owners` in the `build_stamp_annotations` call.

### `scripts/blast-radius.sh` (the reference consumer — the **D** of this work)
- Read `io.houba.owners`, `split(",")`.
- "Who to page" rollup is multi-owner: an image with N owners counts in each of
  its N owner groups.
- Rename `BLAST_TEAM` → `BLAST_OWNER`; filter by **membership** (does the image
  carry this owner?) instead of equality.
- Inventory column `TEAM` → `OWNERS` (joined).

### Docs / examples / architecture (kept in sync, per CLAUDE.md)
- `docs/examples/reference/busybox/busybox.yml` and
  `.../debian-tz/debian-tz.yml`: migrate `metadata.labels.team` → `owners`
  (show both a `defaults` owner and a per-import override).
- `docs/examples/README.md`: update the walkthrough (new key, multi-owner
  rollup, `BLAST_OWNER`).
- ADR under `docs/architecture/decisions/`: the clean contract break
  (`io.houba.owner.team` → `io.houba.owners`, multi-valued, source = `owners`
  field), linking this spec.
- `docs/architecture/design.md`: mention `io.houba.owners` where `owner.team`
  is described.
- C4 `workspace.dsl`: **no change** — Backstage is a future integration, not
  wired now; no new actor/external system at context/landscape level.

### Tests (TDD, one behavior per commit)
- `tests/unit/domain/test_stamp.py`: owners joined into `io.houba.owners`;
  omitted when empty; `owner.team` no longer emitted.
- `tests/unit/domain/test_mirror_policy.py`: parse `owners` on defaults +
  import; reject malformed owner refs.
- `tests/unit/domain/test_policy_merge.py`: defaults→import override.
- `tests/unit/use_cases/test_reconcile.py`: resolved owners land in the stamp;
  update the existing `owner.team` assertion to `io.houba.owners`.
- Coverage gates hold: ≥ 90 % `houba.domain`, ≥ 80 % global.

## Out of scope

- Making `owners` mandatory (enforcement).
- Branching a real Backstage catalog (resolution/validation against the
  catalog) — the string format is chosen to make this a later, migration-free
  step.
- Org hierarchy (tribe/BU) and escalation contacts (Slack/PagerDuty) — other
  facets of "ownership is too thin", not pursued here.
