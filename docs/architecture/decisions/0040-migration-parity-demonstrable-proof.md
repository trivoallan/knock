# 40. Migration parity is proven, not just asserted — placement keeps the referrer

Date: 2026-06-23

## Status

Accepted (P0). Implements the *demonstrable* half of the migration-parity *Now* item; the narrative
prose shipped in #156 (`docs/how-to/migrate-from-replication.md`). Full design:
[`docs/superpowers/specs/2026-06-23-migration-parity-demonstrable-proof-design.md`](../../superpowers/specs/2026-06-23-migration-parity-demonstrable-proof-design.md).

## Context

The migration-parity claim — houba's `destinations` fan-out *replaces* registry replication and keeps
the SBOM/signature referrer alive in every team copy — was asserted in prose but never *run*: all
shipped examples fan to a single destination. Registry replication strips OCI 1.1 referrers
([goharbor/harbor#23210](https://github.com/goharbor/harbor/issues/23210)); a claim a stakeholder
cannot watch is not an adoption proof.

## Decision

Ship a runnable proof, **zero houba-core** (multi-`destinations` already ships):

- a multi-destination example (`docs/examples/migration/redis.yml`, two team projects), and
- `scripts/migration-parity-proof.sh` (regctl-only) that, after `houba reconcile`, asserts a
  package-SBOM referrer on the placed digest of *every* team copy and exits non-zero, naming any bare
  copy.

The proof demonstrates houba's **positive** — placement attaches referrers everywhere. It does **not**
stand up Harbor to reproduce replication *stripping*: that is an external documented fact, and the demo
Zot propagates referrers regardless. The cosign signature tier is asserted only when a signer is
configured; an SBOM-only pass is valid (the signed tier is independently demonstrated, ADR 0029).

## Consequences

- **No C4 change** — no new actor or external system; the proof composes existing houba + Zot +
  regctl. No new port / adapter / use case / domain concern — multi-`destinations` is existing
  behaviour.
- The how-to gains a "Prove it" section linking the example + script, so the doc and the runnable
  artifact agree (examples-in-sync, per the engineering conventions).
- A replication-rule → `destinations` importer stays *Deferred* (Declaration scaffolding ⑥) — the
  example/script shapes are kept so an importer could target them later.
