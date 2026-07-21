# Retention-driven soft-delete — a second mark source feeding the reaper

**Status:** approved (design)
**Date:** 2026-06-14
**Related:** [`2026-06-12-delegated-tag-deletion-design.md`](2026-06-12-delegated-tag-deletion-design.md) (the `pending-deletion` referrer + mark/unmark this extends); [`2026-06-13-purge-reaper-design.md`](2026-06-13-purge-reaper-design.md) (the reaper that consumes the marks — unchanged here); roadmap item ⑤ *Lifecycle — `archive_purge`/`archive_restore`*.

> Written in English to match the rest of `docs/` and the public-repo convention. Field and command names are the public API.

---

## 1. Problem

knock removes a tag along **one axis only**: *selection*. When a tag falls out of a policy's include/exclude set, `reconcile_import` puts it in `to_delete`, and the use case either hard-deletes it (`deletionMode: purge`) or attaches a `pending-deletion` referrer for the reaper (`deletionMode: mark`).

Nothing caps **valid, in-selection** tags. A policy that mirrors every patch release (`includeRegex: "^7\\.2\\."`) accumulates them forever: each is in `desired`, so `reconcile` never marks it. The `MirrorPolicy` schema already carries the retention knobs for exactly this — `Archive{keep, olderThanDays}` on `ImportProfile`/`Defaults` — but **nothing consumes them**. They are dormant, inherited from the Groovy lineage.

This is roadmap ⑤'s remaining gap. The original Groovy `archive_purge` moved old images to cold storage; knock's `purge` reaper instead re-interpreted "archive_purge" as a usage-gated *delete*. The retention axis was left unbuilt.

## 2. Goal & the decision that shaped it

Activate `Archive{keep, olderThanDays}` as a **second source of `pending-deletion` marks**, computed inside `reconcile`, distinguished from the selection axis only by `reason`.

We deliberately rejected a separate cold-storage "attic" (copy-out + a `knock restore` to copy back). In the chosen **same-registry** world it buys no bytes (shared, deduplicated blobs) and the existing soft-delete already delivers reversible removal *better* than a copy would — the tag stays pullable while marked. The honest differentiator of retention is **the trigger, not a new store**: it reaches *valid* tags the selection axis structurally cannot. So retention simply *feeds the proven mark→reaper pipeline* — no copy-back, and no rescue/restore command (see Non-goals).

Result: no new command, no new port/adapter, no copy — one pure domain function, two new `reconcile` fields, a reason-aware mark/unmark, and a small `global ← policy` threshold cascade.

## 3. Design

### 3.1 The pure core — `select_retention_excess`

`knock/domain/retention.py` (new, pure, ≥ 90 % coverage):

```python
def select_retention_excess(
    kept: dict[str, datetime],          # desired+present output tags → import time
    *,
    keep: int,
    older_than: timedelta,
    now: datetime,
    protected: frozenset[str] = frozenset(),
) -> list[str]:
    """Tags eligible for a retention mark: ranked by import time descending,
    a tag is eligible iff (rank >= keep) AND (now - imported_at > older_than)
    AND (tag not in protected). Returns the eligible tags, sorted."""
```

- **AND, not OR.** `keep` is the primary guard (always retain the N most-recently-imported); `older_than` is a safety delay on top (do not demote even the `(keep+1)`-th until it has aged). A tag is marked only when *both* agree.
- **Ranking metric = import time** (see 3.3), reused for the age test — one timestamp, two uses.
- **`protected`** excludes tags that must never be retention-marked: **alias targets** (`latest`→`1.2.3` must not demote `1.2.3`).

### 3.2 Domain wiring — `knock/domain/reconcile.py`

- `MirrorArtifact` gains `imported_at: datetime | None`.
- `ImportReconcile` gains `to_mark_retention: list[str]` and `to_unmark_retention: list[str]`.
- `reconcile_import`'s `marked: set[str]` is split into **`marked_selection`** and **`marked_retention`** (the use case partitions referrers by `reason`); it gains a `retention` parameter (the effective, cascade-resolved thresholds — see §3.6).

Per variant, the *kept* set = desired **concrete** output tags (excluding aliases) present in `mirror`, each mapped to its `imported_at`; that variant's **alias targets** (suffixed) form its `protected` set, computed internally. Then:

```
to_delete           = sorted(t for t in mirror if t not in desired)        # unchanged (selection)
retention_excess    = ⋃ over variants of select_retention_excess(kept_v, keep, older_than, now, protected=alias_targets_v)
to_mark_retention   = sorted(retention_excess − marked_retention)          # idempotent
to_unmark_retention = sorted(marked_retention − retention_excess)          # no longer excess ⇒ clear
to_unmark           = sorted(t for t in marked_selection if t in desired)  # unchanged (selection re-entry)
```

`retention_excess ⊂ desired`; `to_delete ⊄ desired` — the two axes are **disjoint** by construction. `Archive` is read from the expanded import; `archive is None` ⇒ retention skipped entirely. `protected` (alias targets) is consumed by `select_retention_excess` only.

### 3.3 Why import time, and from where

`older_than` and the rank both use **when knock stamped the tag**, read from the OCI-standard `org.opencontainers.image.created` annotation that `build_stamp_annotations(created=now, …)` writes at import — on **both** the copy and rebuild paths. This is "age in our mirror", which is what retention means — not `ImageInfo.created` (the manifest config's build time, which on the copy path is the *upstream* build date and would mis-age a freshly-mirrored-but-old image).

`to_mirror_artifact` already returns `None` for any tag lacking the knock stamp, so **the mirror set is 100 % stamped** and the annotation is always present. A tag whose annotation is missing or unparseable is conservatively **excluded** from retention (never marked).

### 3.4 Use-case wiring — `_apply_plan`

`_apply_plan` already inspects every mirror tag, so `imported_at` costs **no extra registry call** (parsed from the annotations it already fetches). Changes:

1. **Partition marks by reason.** It already fetches `marked_referrers` per tag (`list_referrers(…, PENDING_DELETION_ARTIFACT_TYPE)`); read each referrer's `{prefix}.lifecycle.reason` to split into `marked_selection` / `marked_retention`.
2. **Stage 3 gains retention marking.** Alongside the selection mark/delete, mark `result.to_mark_retention` with `reason="retention-excess"` (skip already-marked → idempotent) and clear `result.to_unmark_retention`.
3. **Reason-aware unmark.** The existing blanket auto-unmark (`marked ∩ desired`) is now scoped to **selection** marks. Retention marks are cleared **only** via `to_unmark_retention` (no longer excess), never merely for being `∩ desired` — otherwise every retention mark would self-erase next run (retention marks live *on* desired tags).

### 3.5 Retention always marks — never hard-deletes

Retention emits **only** `pending-deletion` marks, **independent of `deletionMode`** — even under `deletionMode: purge`. Deleting a *valid* tag (merely old) with no usage gate is unacceptable; retention removal must always pass through the usage-gated reaper.

**Consequence:** retention presupposes a scheduled reaper (`knock purge`). Without one, retention marks accumulate harmlessly — the tags stay fully pullable — but are never reaped. Documented as an operational prerequisite. This keeps retention purely additive and safe to ship: it never deletes anything directly; it only attaches a reversible, reaper-gated mark.

### 3.6 Threshold resolution, granularity & opt-in

- **Cascade `global ← policy`, per field.** `keep` and `olderThanDays` resolve most-specific-wins across **two** levels: a policy's `Archive` (on `ImportProfile`/`Defaults`, already merged by `policy_merge`) over a **global** `Archive` from `Settings` (`KNOCK_RETENTION` — a JSON object → `Archive | None`, default `None`). A pure `resolve_archive(policy, global_) -> Archive | None` (mirroring `resolve_deletion_mode`) picks **each field** policy-first, then global, then a constant fallback (`DEFAULT_KEEP = 2`, `DEFAULT_OLDER_THAN_DAYS = 30`). To make "unset at a level" distinguishable from a value, `Archive.keep` / `older_than_days` become `int | None = None` (the concrete `2` / `30` move to the constants). Two levels only — no destination tier (retention is a policy/global concern, unlike `deletionMode`).
- **Opt-in / enablement.** Retention is active for an import iff `resolve_archive` returns non-`None` — i.e. either level sets a threshold. **Global `None` (the default) ⇒ retention off fleet-wide**, so untouched deployments are unaffected; setting `KNOCK_RETENTION` turns it on across the fleet, and a policy refines thresholds per field. (A per-policy hard opt-out while global is on — an `archive.enabled: false` — is a future nicety; today a policy can neutralise retention with large thresholds.)
- **`keep N` is per `(dest_repo, variant)`.** Variants (`-eu`, `-us`) are distinct streams; keep N newest *of each*. `_apply_plan` already runs per `(policy, dest_repo)`; the per-variant split is the kept-set construction.

### 3.7 Reporting

Retention marks emit the existing `kind="marked"` operation; the mark work item / `OperationEvent` carries the `reason`, so a run's structured log distinguishes `retention-excess` from `dropped-from-selection`. Clearing `to_unmark_retention` is a quiet cleanup (debug log), mirroring the existing auto-unmark.

## 4. Ports, adapters, config

**One new config var, no new port/adapter.** Reuses `list_referrers` / `put_referrer` / `delete_referrer` (#41) and the existing inspect/annotate. `Settings` gains **`KNOCK_RETENTION`** (JSON → global `Archive | None`, default `None`) — the global tier of the §3.6 cascade, read only in `config.py`. The reaper (`knock purge`) is **unchanged** (it consumes both reasons identically).

## 5. Architecture sync (required by CLAUDE.md)

- **C4.** No new actor / external system / integration — context and landscape are unchanged. Internal: a new **domain concern** (`domain/retention.py`) and a `MirrorArtifact` field — no new port/adapter pair, no layer-boundary change. The **Component** view gains the `select_retention_excess` function under `domain/`; that edit lands with the implementation PR (noted here so it is a recorded decision, not drift). Mirrored as thin ADR [`0017-retention-marking.md`](../../architecture/decisions/0017-retention-marking.md).
- **Schemas.** `Archive.keep` / `older_than_days` become nullable and `Settings` gains `KNOCK_RETENTION`; both the **policy** and **config** JSON Schemas regenerate from the models (`model_json_schema()`), never hand-written.
- **Examples.** [`docs/examples/retention/redis.yml`](../../examples/retention/redis.yml) — a `MirrorPolicy` with `archive: {keep, olderThanDays}` — added here, marked **design-stage** until the feature lands; the README walkthrough (excess valid tags get a `retention-excess` mark → `knock purge` reaps the unused) lands with the implementation.

## 6. Testing & verification (strict TDD)

- **Domain** (`tests/unit/domain/`): `select_retention_excess` — AND vs each guard alone, import-time ranking, `keep` boundary, age boundary, `protected` exclusion, empty inputs. `reconcile_import` — `to_mark_retention`/`to_unmark_retention` set algebra; disjointness from `to_delete`; effective `archive` `None` ⇒ empty; alias targets protected. `resolve_archive` — per-field cascade (policy wins; falls to global; falls to the `DEFAULT_*` constant; both `None` ⇒ `None`/off).
- **Use-case** (`tests/unit/use_cases/`): reason partition of seeded referrers; retention mark applied with `reason="retention-excess"` and idempotent; **reason-aware unmark** (a still-excess retention mark survives; a no-longer-excess one clears; a re-entered selection mark clears); retention marks even under `deletionMode: purge`; `dry_run_deletions` suppresses; `archive=None` ⇒ nothing.
- **Integration:** none new — reuses the `regctl` fake-bin referrer scenarios from #41.
- Coverage gates unchanged: ≥ 80 % global, ≥ 90 % `knock.domain`.

## 7. Non-goals

- **No cold-storage attic, no `knock archive`/`restore` copy command.** Retention feeds the existing soft-delete.
- **No manual rescue / pin / undelete.** Out of scope: the usage-gated reaper already protects in-use content, and selection re-entry auto-unmarks. A durable per-artifact hold can be revisited later if a real need appears.
- **No reaper change.** `knock purge` consumes retention marks unchanged.
- **No destination-level retention tier.** Thresholds cascade `global ← policy` only (§3.6); no per-destination override (unlike `deletionMode`).
- **No deletion by retention.** Retention only ever marks (§3.5).

## 8. Risks

- **Retention without a reaper.** Marks accumulate (harmless) but nothing is reaped. Mitigation: documented prerequisite; the marks keep tags fully pullable, so the failure mode is "no hygiene", not "broken pulls".
- **Reason staleness across axis transitions.** A retention-marked tag that later drops from selection keeps its `retention-excess` reason while becoming a selection candidate. Harmless: the reaper deletes-if-unused regardless of reason; the reason is audit metadata only. Accepted, not fixed.
- **Clock basis of `imported_at`.** Age uses knock's own stamp time; consistent within a deployment, not upstream-dependent.
