# 8. local-transform demo tier

Date: 2026-06-12

## Status

Superseded by [23. Single Argo reference deployment that is the demo](0023-single-argo-reference-deployment.md)
— the three local demo tiers collapse to one `overlays/local`.

Originally accepted; builds on [2. Image transform / hardening — the rebuild path](0002-image-transform-hardening.md)
Extends [4. Reference deployment (kind)](0004-reference-deployment.md)

## Context

The demo tiers sat at opposite ends of a gap: `local-lite` (copy only, never runs a
transform) and `local-full` (rebuild, but needs an externally-installed Harbor plus org
CA/mirror config). There was no lightweight way to watch a transform actually run.

## Decision

Add a self-contained `local-transform` overlay that runs a real transform without Harbor:
`buildkitd` pushing to an in-cluster plain-HTTP `registry:2`, plus a timezone example.

## Consequences

The rebuild + stamp story is demoable with zero external dependencies or org config.
Delivered in #32.

Full design spec: [2026-06-12-local-transform-demo-design.md](../../superpowers/specs/2026-06-12-local-transform-demo-design.md)
