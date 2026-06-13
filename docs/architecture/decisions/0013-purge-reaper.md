# 0013 — `houba purge`: houba ships the reference reaper

**Status:** Accepted
**Date:** 2026-06-13
**Full spec:** [docs/superpowers/specs/2026-06-13-purge-reaper-design.md](../../superpowers/specs/2026-06-13-purge-reaper-design.md)

## Context

#41 (ADR 0012) delegates tag deletion to an "external reaper" and declares houba
never executes a delegated purge. Something must be the reaper, or marks
accumulate forever.

## Decision

Ship the reaper as `houba purge`, isolated behind its own `UsageOraclePort` and
use case (discipline B, replaceable). It asks the observability stack a
stateless, point-in-time question (was this digest seen in prod within an idle
window?) and purges only the unused. This revises #41's "external system"
non-goal honestly: asking ≠ watching; houba stores no fleet state.

## Consequences

- A new external system (the usage oracle) is queried by houba; "Datadog" is a
  generic command (`HOUBA_USAGE_ORACLE_CMD`), not in-tree code.
- New `RegistryPort.list_repositories` (catalog-walk root).
- Fail-closed by default; `HOUBA_PURGE_MIN_IDLE_DAYS` and the oracle command are
  both required (else `ConfigError`).
- Builds on #41 (consumes its `pending-deletion` referrer + artifactType).
