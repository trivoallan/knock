# 2. Image transform / hardening — the rebuild path

Date: 2026-06-11

## Status

Accepted

Builds on [1. MirrorPolicy format & reconcile contract](0001-mirror-policy-format.md)

## Context

v0.2.0 ships the **copy path** — mirror + provenance stamp via `regctl`. Organisation
hardening (internal CA trust, internal package mirrors) previously lived in org-specific
Groovy scripts baked into the pipeline — not portable, not auditable.

## Decision

Add the **rebuild path**: re-build a source image through a declarative hardening policy
and stamp the result with transform lineage. Two primitives — `injectCA` and
`rewritePackageSources` — resolved by name from env-rosters; the org-specific scripts
become *configuration* of generic, composable primitives, never hardcoded behaviour.

## Consequences

A policy variant carrying a non-empty `transform` is rebuilt (BuildKit) instead of
byte-copied; hardening is auditable config. Delivered in #24.

Full design spec: [2026-06-11-image-transform-hardening-design.md](../../superpowers/specs/2026-06-11-image-transform-hardening-design.md)
