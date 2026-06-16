# 28. Scan-referrer garbage collection (`houba gc`)

Date: 2026-06-16

## Status

Accepted.

## Context

Every `houba attach` writes a fresh `application/vnd.houba.scan.result.v1` referrer onto the
subject. Re-scanning the same image — the normal cadence as new CVEs land and CI re-runs —
accumulates superseded referrers without bound. The scan stamp is part of the product surface, yet
nothing ever removes the stale ones. This was the last feature-side roadmap item.

## Decision

A new `houba gc` verb walks the registry roster (sequentially, v1) and deletes superseded
scan-result referrers. Retention is **per `(tool, format)`**: keep the N newest per group, and only
collect those older than `--older-than-days` (both conditions). The decision is pure domain
(`domain/scan/gc.select_superseded_referrers`), reusing the keep-N + older-than model from
`domain/retention`. Dry-run by default; `--apply` to delete; `HOUBA_DRY_RUN_DELETIONS` is the
deployment-wide kill-switch. No usage oracle — the decision is purely temporal/local. Registry-config
parity with reconcile / audit / purge / attach (`HOUBA_REGISTRIES` roster + `--registry` override,
via the shared `ensure_registry_session`). Per-subject failures redden the exit without blocking
siblings.

## Non-goals (v1)

Reaping the paired cosign attestation (correlation requires parsing signed DSSE predicates — a
collected report can leave an orphan attestation, tracked as a follow-up); concurrent / sharded walk;
per-policy retention thresholds.

## Consequences

- New verb in the lineup: `reconcile · purge · attach · audit · version · gc`.
- No new port, env var schema, or Pydantic policy model — thresholds are CLI flags.

Full design spec:
[2026-06-16-scan-referrer-gc-design.md](../../superpowers/specs/2026-06-16-scan-referrer-gc-design.md)
