# 1. MirrorPolicy format & reconcile contract

Date: 2026-05-22

## Status

Accepted

## Context

houba is a stamper / single front door for external OCI artifacts: it pulls upstream
images, optionally rebuilds them through a hardening policy, and stamps them with
portable provenance. It needs a declarative, per-product contract describing what to
mirror, where to, and how — plus a deterministic command to apply it.

## Decision

Adopt a declarative `MirrorPolicy` YAML schema (`apiVersion: houba.io/v1alpha1`) as the
product's public API: `source` + `imports` (tag selection → destinations) + optional
`transform`, with named-registry resolution from an env-roster (`HOUBA_REGISTRIES`).
`houba reconcile <dir>` loads and applies these policies. The Pydantic models are the
single source of truth; the JSON Schema is derived from them, never hand-written.

## Consequences

The policy file is the declarative contract editors and CI validate against; new
behaviour extends the schema before adding imperative branching. Delivered in v0.2.0+.

Full design spec: [2026-05-22-mirror-policy-format-design.md](../../superpowers/specs/2026-05-22-mirror-policy-format-design.md)
