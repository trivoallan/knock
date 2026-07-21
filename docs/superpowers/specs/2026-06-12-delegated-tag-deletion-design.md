# Delegated tag deletion — soft-delete via OCI referrer, purge owned by an external reaper

**Status:** approved (design)
**Date:** 2026-06-12
**Related:** [`2026-06-11-reconcile-output-design.md`](2026-06-11-reconcile-output-design.md) (the `to_delete` plan this extends); roadmap item ⑤ *Lifecycle — `archive_purge`/`archive_restore`*.

## Problem

When a tag falls out of a policy's desired set (the include/exclude regex tightened, an alias was
removed), `reconcile_import` puts it in `to_delete` and the reconcile use case **hard-deletes** it
immediately (`registry.delete_tag` → `regctl tag rm`), gated only by `dry_run_deletions`.

But knock has **no visibility into what is deployed**. A tag that left the policy may still be
running in production. knock unilaterally removing it can break a live pull-by-tag. The authority
that *can* answer "is this image still used in prod?" is an **external system** (the org's
deployment/observability stack), not knock.

So knock should be able to **delegate deletion**: instead of removing the tag, mark it as a
*candidate for deletion* and let an external **reaper** — which sees prod usage — verify and purge.

## Goal

Add a **deletion mode** resolved through a three-level cascade:

- **`purge`** (today's behaviour) — hard-delete unchanged.
- **`mark`** — attach a `pending-deletion` **OCI referrer** to the manifest. The image digest stays
  **immutable** and the tag stays **pullable**; the only change is a small attached artifact. An
  external reaper discovers candidates by querying the referrers API filtered on knock's
  `artifactType`, then owns the verify-and-purge decision.

The effective mode for each **(policy, target registry)** pair is resolved **most-specific-wins**:
**policy → destination → global**. Only the global level carries a concrete default (`purge`), so an
untouched deployment keeps today's behaviour.

knock stays a **signal emitter**, never the executor of a delegated deletion — perfectly aligned
with the product thesis ("the label is the product", blast-radius = one query in observability).

## Design

### Deletion mode — three-level cascade

One `DeletionMode` enum, declared in three optional places; the effective mode is resolved
most-specific-wins per (policy, target registry).

```python
class DeletionMode(StrEnum):
    purge = "purge"
    mark = "mark"
```

1. **global** — `Settings.deletion_mode` (`KNOCK_DELETION_MODE`, `config.py`), the only level with a
   concrete default: `DeletionMode.purge`. Org-wide baseline. Untouched ⇒ today's behaviour.
2. **destination** — `RegistryConfig.deletion_mode: DeletionMode | None = None`, a new key inside the
   `KNOCK_REGISTRIES` JSON, keyed by registry host. "Does *this* registry's environment have a
   reaper?" lives here.
3. **policy** — `MirrorPolicy.spec.deletion_mode: DeletionMode | None = None`. **Default `None`**, not
   `purge` — a concrete default here would short-circuit the cascade and the lower levels could never
   apply. The policy author opts a specific product in/out only when they mean to.

The JSON Schema is regenerated from the models (`model_json_schema()`), per "derive, never
hand-write".

#### Resolution — a pure domain function

`knock/domain/deletion_mode.py`:

```python
def resolve_deletion_mode(
    policy: DeletionMode | None,
    destination: DeletionMode | None,
    global_: DeletionMode,        # always concrete (Settings default = purge)
) -> DeletionMode:
    return policy or destination or global_
```

Pure and trivially testable. The reconcile use case already iterates per destination/target; for
each target it looks up that registry host's `RegistryConfig.deletion_mode`, the policy's
`spec.deletion_mode`, and the global `Settings.deletion_mode`, calls `resolve_deletion_mode`, and
passes the concrete result down to the per-target lifecycle logic.

### Domain (`knock/domain/reconcile.py`) — pure, mode-agnostic

`reconcile_import` (and the type returned) gain knowledge of the **already-marked** mirror tags so
it can stay idempotent and compute reversals. The mode itself does **not** enter the domain — the
domain computes set relationships, the use case applies the mode.

New input: `marked: set[str]` — mirror output-tags currently carrying a knock `pending-deletion`
referrer (the use case fetches this; see ports).

`ImportReconcile` gains `to_unmark`:

```python
@dataclass(frozen=True)
class ImportReconcile:
    name: str
    variants: list[VariantReconcile]
    to_delete: list[str]   # unchanged: undesired = mirror tags not in desired
    to_unmark: list[str]   # marked ∩ desired — tags that re-entered; clear the stale mark
```

Computation:

```python
undesired = {t for t in mirror if t not in desired}
to_delete = sorted(undesired)                 # unchanged
to_unmark = sorted(t for t in marked if t in desired)
```

The use case then, per `deletion_mode`:

- **`purge`** → `delete_tag` over `to_delete` (today's path), and `delete_referrer` over `to_unmark`
  to clear any stale mark left by a prior `mark` run on a tag that has since re-entered the policy.
  (A still-undesired marked tag is simply hard-deleted, its referrer going with the manifest.)
- **`mark`** → `put_referrer` over `to_delete − marked` (skip already-marked: idempotent), and
  `delete_referrer` over `to_unmark` (**auto-unmark**: a tag that came back is kept).

`domain/` coverage stays ≥ 90 %.

### Pending-deletion payload (`knock/domain/` — pure, sibling of `stamp.py`)

A new pure function `build_pending_deletion_annotations(prefix, *, marked_at, reason, policy,
import_, variant)` produces the referrer's annotations, mirroring `build_stamp_annotations`:

- **artifactType:** `application/vnd.knock.lifecycle.pending+json`
- `{prefix}.lifecycle.state = pending-deletion`
- `{prefix}.lifecycle.marked-at` = ISO-8601 from `ClockPort.now()`
- `{prefix}.lifecycle.reason = dropped-from-selection`
- identity reused from the stamp: `{prefix}.policy` / `{prefix}.import` / `{prefix}.variant`
- **no timing field** — `marked-at` is a *fact*, not a deadline; the reaper owns timing.

`prefix` is `KNOCK_LABEL_PREFIX` (default `io.knock`); an empty prefix emits only `marked-at` /
`reason` / `state` under bare `lifecycle.*` keys, consistent with the stamp's empty-prefix rule.
This payload is designed to fold into the upcoming **provenance-schema freeze** (roadmap ①).

### Ports & adapters

`RegistryPort` (`knock/ports/registry.py`) gains three methods and a frozen data model:

```python
@dataclass(frozen=True)
class Referrer:
    digest: str                 # the referrer manifest digest
    artifact_type: str
    annotations: dict[str, str]
    subject_tag: str            # the output-tag whose manifest it refers to

class RegistryPort(Protocol):
    ...
    def list_referrers(self, image_ref: str, artifact_type: str) -> list[Referrer]: ...
    def put_referrer(self, image_ref: str, artifact_type: str,
                     annotations: dict[str, str]) -> None: ...
    def delete_referrer(self, referrer_ref: str) -> None: ...
```

`RegctlAdapter` (`knock/adapters/regctl_cli.py`) implements them over verified regctl commands:

- `list_referrers` → `regctl artifact list <repo>:<tag> --filter-artifact-type <type> --format '{{json .}}'`
- `put_referrer` → `regctl artifact put --subject <repo>:<tag> --artifact-type <type> --annotation k=v …`
- `delete_referrer` → `regctl manifest delete <repo>@<digest>`

Failures raise `RegctlError` (no retry, per the adapter rule). The use case fetches the current
`marked` set by calling `list_referrers` for each output tag (or per repo) filtered on the knock
`artifactType`, feeding `reconcile_import`.

### Observability (`knock/ports/reporter.py`)

`OperationKind` gains `"marked"`. The use case emits one `OperationEvent(kind="marked", …)` per
newly-marked tag (so a run's structured log and counts surface the soft-deletes). **Auto-unmark is a
quiet cleanup** (debug log only, no dedicated event kind) — matching the "auto-unmark" choice
without the extra event surface. `Counts` gains a `marked` field for the summary.

### Dry-run

The existing `dry_run_deletions` flag gates the **whole lifecycle pathway**: in `purge` mode it
skips `delete_tag` (today); in `mark` mode it skips `put_referrer`/`delete_referrer`. No new env
var — marking is the deletion path's delegated form, so it shares the gate.

## Non-goals

- **knock never executes a delegated purge.** Removing a `mark`ed tag is entirely the reaper's job;
  knock only adds/clears the marker. (`purge` mode is the *non-delegated* path and is unchanged.)
- **No reaper implementation.** This spec defines the contract (the referrer + artifactType the
  reaper reads); the reaper is an external system.
- **No timing/TTL emitted by knock.** No `not-before`, no grace on deletion. The import-side 7-day
  stability window is unrelated and untouched.
- **No cross-registry mark replication.** If marks must reach replica registries, the reaper queries
  each registry directly (see Risks — Harbor referrer replication).

## Architecture sync (required by CLAUDE.md)

- **C4 — a new external system + integration.** The **external reaper / deletion authority** is a
  new actor at System Context and Landscape level: it reads knock's `pending-deletion` referrers and
  owns purge. `docs/architecture/workspace.dsl` is updated in the same change (the reaper system +
  a "discovers deletion candidates" relationship). The Container/Component views gain the three new
  `RegistryPort` referrer methods on `RegctlAdapter`. Mirrored as a thin ADR
  `docs/architecture/decisions/0012-delegated-tag-deletion.md` linking here.
- **Examples.** Add/extend a `MirrorPolicy` under `docs/examples/` with `deletionMode: mark` plus a
  README walkthrough showing: a tag leaves the policy → a `pending-deletion` referrer appears (digest
  unchanged) → the tag re-enters → the referrer is auto-cleared.

## Testing & verification (strict TDD)

- **Domain unit tests** (`tests/unit/domain/`): `resolve_deletion_mode` cascade (policy wins;
  falls to destination; falls to global; global always concrete); `to_unmark` = `marked ∩ desired`;
  `to_delete` unchanged; idempotence inputs (already-marked tag not re-counted by the use case); the
  pure `build_pending_deletion_annotations` payload (keys, empty-prefix collapse, identity reuse).
- **Use-case tests** (`tests/unit/use_cases/`): with `FakeRegistryPort` journalling `.marked` /
  `.unmarked`, assert `mark` mode marks `to_delete − marked` and unmarks `to_unmark`, `purge` mode
  deletes, and `dry_run_deletions` suppresses both. Cover the **cascade per target**: a policy-level
  `mark` overriding a global `purge`; a destination-level override for one target while another
  target of the same policy falls through to global. Seed pre-existing referrers via the fake's
  constructor.
- **Integration** (`tests/integration/`): extend the `regctl` fake-bin with `artifact list` /
  `artifact put` / `manifest delete` scenarios (branch on `FAKE_REGCTL_SCENARIO`, append argv to
  `FAKE_REGCTL_LOG`) and assert `RegctlAdapter` emits the exact referrer commands.
- Coverage gates unchanged: ≥ 80 % global, ≥ 90 % `knock.domain`.

## Risks

- **Harbor referrer support.** Verified (June 2026): Harbor implements the referrers API and the
  `subject` field; recent versions (2.15.0 cited) store and serve OCI 1.1 referrers pushed via
  ORAS/regctl, and the API supports `artifactType` filtering — so our reaper's
  `referrers?artifactType=application/vnd.knock.lifecycle.pending+json` query works. Known caveats,
  none blocking: (1) **replication** of OCI 1.1 referrers between Harbor instances is unreliable in
  some versions ([goharbor/harbor#23210](https://github.com/goharbor/harbor/issues/23210)) — covered
  by the "reaper queries each registry directly" non-goal; (2) the **Harbor UI** shows custom
  `artifactType` as `UNKNOWN` ([#22592](https://github.com/goharbor/harbor/issues/22592),
  [#21344](https://github.com/goharbor/harbor/issues/21344)) — cosmetic, the reaper uses the API.
  regctl also falls back to the `sha256-<digest>` referrers-tag scheme on registries lacking the
  native endpoint.
- **Stale marks under `purge` after a mode switch.** If a policy flips `mark` → `purge`, previously
  marked-but-still-undesired tags would be hard-deleted on the next run (the mark becomes moot). This
  is the intended semantics (purge is non-delegated) but should be called out in the example README.
- **Referrer accumulation.** Auto-unmark prevents stale marks for tags that return; tags that stay
  undesired keep exactly one mark (idempotent put). The reaper removing the subject also removes the
  referrer (`regctl manifest delete --referrers` semantics).
