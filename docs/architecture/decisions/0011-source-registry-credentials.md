# 11. Source-registry credentials

Date: 2026-06-12

## Status

Accepted

Extends [5. Registry TLS/auth + regctl in the runtime image](0005-registry-tls-and-runtime-image.md)
Supports [8. local-transform demo tier](0008-local-transform-demo.md)

## Context

knock pulled each policy's source image anonymously, so high-volume demos and real deployments
hit Docker Hub's unauthenticated pull rate limit (429) — it blocked the `local-transform` e2e.
Destinations were already authenticated; the source registry was not.

## Decision

Authenticate source pulls via the standard Docker `config.json`: both `buildctl` (rebuild) and
`regctl` (copy) read it natively, so mounting a Docker-auth secret into the knock container is
nearly code-free. Add a `make docker-auth` affordance.

## Consequences

Source pulls authenticate, dodging the rate limit, with almost no new code. Opt-in. Delivered
in #34.

Full design spec: [2026-06-12-source-registry-credentials-design.md](../../superpowers/specs/2026-06-12-source-registry-credentials-design.md)
