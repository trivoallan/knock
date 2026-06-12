# 3. Reconcile output & resilience

Date: 2026-06-11

## Status

Accepted

Refines [1. MirrorPolicy format & reconcile contract](0001-mirror-policy-format.md)

## Context

`houba reconcile` emitted a single summary line, and a single failing policy aborted the
whole run — poor for both machine consumption and multi-policy operation.

## Decision

Replace it with a structured, two-stream output: a machine-readable report on stdout and
an in-flight journal on stderr via a new `Reporter` port. Make the reconciler
accumulate-and-continue per policy. Publish the report's JSON Schema.

## Consequences

Results are scriptable and CI-gateable; one bad policy no longer hides the rest. New
units: `use_cases/report.py`, `ports/reporter.py`, `cli/render.py`. Delivered.

Full design spec: [2026-06-11-reconcile-output-design.md](../../superpowers/specs/2026-06-11-reconcile-output-design.md)
