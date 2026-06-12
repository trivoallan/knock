# 5. Registry TLS/auth + regctl in the runtime image

Date: 2026-06-11

## Status

Accepted

Supports [2. Image transform / hardening — the rebuild path](0002-image-transform-hardening.md)

## Context

houba's whole runtime uses `regctl` as its registry client (list / inspect / copy /
annotate / delete / login). Two gaps blocked real-world operation: the shipped image
could not run `regctl`, and houba could not reach internal-CA or plain-HTTP registries.

## Decision

Bundle `regctl` into the runtime image, and add per-registry TLS/CA configuration
(`tls_verify`, `ca_cert`) resolved from the named-registry roster.

## Consequences

The shipped image is runnable end-to-end, and internal-CA / insecure registries are
reachable without manual host setup. Delivered.

Full design spec: [2026-06-11-registry-tls-and-runtime-image-design.md](../../superpowers/specs/2026-06-11-registry-tls-and-runtime-image-design.md)
