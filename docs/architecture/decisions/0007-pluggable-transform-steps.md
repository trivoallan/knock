# 7. Pluggable transform-step registry

Date: 2026-06-11

## Status

Accepted

Refines [2. Image transform / hardening — the rebuild path](0002-image-transform-hardening.md)

## Context

#24 shipped the rebuild path with two built-in primitives (`injectCA`,
`rewritePackageSources`) and a resource-kind switch in the application layer — adding a
hardening step meant editing the orchestrator.

## Decision

Refactor transforms into a pluggable step registry (`domain/transforms/`, pure) with a
discriminated-union JSON Schema and reference step compilers. A new step is a plug-in;
the only remaining switch is resource-kind resolution.

## Consequences

New hardening steps are declarative, schema-validated plug-ins; the orchestrator stays
closed for modification. Delivered.

Full design spec: [2026-06-11-transform-steps-pluggables-design.md](../../superpowers/specs/2026-06-11-transform-steps-pluggables-design.md)
