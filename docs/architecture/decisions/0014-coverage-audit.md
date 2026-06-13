# 14. Coverage audit (houba audit)

Date: 2026-06-13

## Status

Accepted

Builds on [1. MirrorPolicy format & reconcile contract](0001-mirror-policy-format.md) and the
provenance stamp ([6. SLSA / in-toto attestation](0006-slsa-attestation.md)).

## Context

The roadmap's coverage-gate thesis: houba's value is proportional to it being the *mandatory*
front door. Roadmap ④ makes coverage measurable — "show me the registry images that do NOT
carry houba's stamp" — which is what makes the front door verifiable, and therefore enforceable.

## Decision

Add a read-only `houba audit` verb: a whole-registry catalog walk (reusing the `purge` pattern)
that classifies each image via a pure `domain/coverage.py:is_stamped` predicate (annotation
stamp: `{prefix}.policy`, or `base.digest` when the prefix is empty) and emits a `CoverageReport`.
A new lightweight `RegistryPort.get_annotations` (one `manifest get`) keeps the sweep cheap.
Report-only by default; `--fail-on-uncovered` is an opt-in CI gate; per-image read errors redden
the exit independently.

## Consequences

Coverage becomes measurable and CI-gateable. v1 is annotation-stamp only (the signed-attestation
coverage tier is a follow-up once the copy path is also attested) and sequential (concurrency
deferred, like purge).

Full design spec: [2026-06-13-coverage-audit-design.md](../../superpowers/specs/2026-06-13-coverage-audit-design.md)
