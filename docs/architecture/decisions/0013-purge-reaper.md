# 0013 — `knock purge`: knock ships the reference reaper

**Status:** Accepted
**Date:** 2026-06-13
**Full spec:** [docs/superpowers/specs/2026-06-13-purge-reaper-design.md](../../superpowers/specs/2026-06-13-purge-reaper-design.md)

## Context

#41 (ADR 0012) delegates tag deletion to an "external reaper" and declares knock
never executes a delegated purge. Something must be the reaper, or marks
accumulate forever.

## Decision

Ship the reaper as `knock purge`, isolated behind its own `UsageOraclePort` and
use case (discipline B, replaceable). It asks the observability stack a
stateless, point-in-time question (was this digest seen in prod within an idle
window?) and purges only the unused. This revises #41's "external system"
non-goal honestly: asking ≠ watching; knock stores no fleet state.

## Consequences

- A new external system (the usage oracle) is queried by knock; "Datadog" is a
  generic command (`KNOCK_USAGE_ORACLE_CMD`), not in-tree code.
- New `RegistryPort.list_repositories` (catalog-walk root).
- Fail-closed by default; `KNOCK_PURGE_MIN_IDLE_DAYS` and the oracle command are
  both required (else `ConfigError`).
- Builds on #41 (consumes its `pending-deletion` referrer + artifactType).
