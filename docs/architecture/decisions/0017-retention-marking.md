# 0017 — Retention-driven soft-delete: a second mark source

**Status:** Accepted
**Date:** 2026-06-14
**Full spec:** [docs/superpowers/specs/2026-06-14-retention-marking-design.md](../../superpowers/specs/2026-06-14-retention-marking-design.md)

## Context

The `MirrorPolicy` schema carries `Archive{keep, olderThanDays}` but nothing consumes it — dormant since the Groovy lineage. knock removes tags only along the *selection* axis (#41); valid, in-selection tags accumulate unbounded. This is roadmap ⑤'s retention gap. A cold-storage "attic" + copy-back was considered and rejected: in the same-registry world it saves no bytes (deduplicated blobs) and the existing soft-delete already gives reversible removal — better, with the tag still pullable while marked.

## Decision

Activate `Archive{keep, olderThanDays}` as a **second source of `pending-deletion` marks**, computed in `reconcile` (`domain/retention.py`), distinguished from selection only by `reason="retention-excess"`. Retention **always marks, never hard-deletes** (even under `deletionMode: purge`) — removing a merely-old valid tag must pass the usage-gated reaper. Age is "time since knock stamped it" (the `org.opencontainers.image.created` annotation), not the upstream build time. Thresholds (`keep` / `olderThanDays`) resolve **global ← policy**: a `KNOCK_RETENTION` global `Archive`, overridden per field by the policy's `Archive`. No copy-back and no rescue command are in scope.

## Consequences

- No new command, port, or adapter; one new config var (`KNOCK_RETENTION`). The reaper (`knock purge`) is unchanged (it consumes both reasons).
- Unmark becomes **reason-aware**: retention marks clear only when no longer excess, never merely for being in `desired`.
- `MirrorArtifact` gains `imported_at`; `reconcile_import` gains `to_mark_retention` / `to_unmark_retention` and a `protected` set (alias targets).
- Thresholds cascade `global ← policy` via a pure `resolve_archive`; `Archive` fields become `int | None`; the policy and config JSON Schemas regenerate.
- Retention presupposes a scheduled reaper; without one, marks accumulate harmlessly.
- Off by default: `KNOCK_RETENTION` unset and no policy `archive:` ⇒ unchanged behaviour. Setting the global var enables retention fleet-wide (policy overrides per field).
