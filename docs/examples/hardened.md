---
title: "Hardened rebuild"
description: "Rebuild path with org hardening: inject internal CA, rewrite package sources."
sidebar_position: 3
---

The rebuild path with org hardening: inject internal CA certs (`injectCA`) and rewrite package sources to an internal mirror (`rewritePackageSources`), then stamp the result. The transform engine is implemented; running it needs a BuildKit daemon (`buildctl`) plus org-specific config (`HOUBA_TRANSFORM_CA_CERTS` / `HOUBA_TRANSFORM_PACKAGE_MIRRORS`). See [Transforms & signed attestations](../explanation/attestations.md) for the full walkthrough.

```yaml title="docs/examples/hardened/redis.yml"
# Hardening (rebuild path) — uses the transform engine (delivered).
# Design: docs/superpowers/specs/2026-06-11-image-transform-hardening-design.md
#
# Unlike the copy-path examples (../busybox, ../redis), this one REBUILDS the image
# through a declarative hardening policy: it injects internal CA certs into the image's
# trust store and rewrites its package sources to an internal mirror, then stamps the
# result (base.digest = source digest, plus io.houba.transform.*). The policy stays
# portable — it only names the CA(s)/mirror; the org-specific data lives in config:
#
#   HOUBA_TRANSFORM_CA_CERTS='{"corp": {"path": "/etc/houba/certs/corp-root.pem"}}'
#   HOUBA_TRANSFORM_PACKAGE_MIRRORS='{"corp": {"apt": "https://mirror.corp/debian", "apk": "https://mirror.corp/alpine"}}'
#
# Run it with `houba reconcile docs/examples/hardened`.
#
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata:
  name: redis-hardened
spec:
  artifactType: image
  source:
    registry: docker.io
    repository: library/redis
  imports:
    - name: v7
      owners:
        - group:default/data-platform     # stamped as io.houba.owners
      tags:
        includeRegex: "^7\\.2\\."
      transform:
        - injectCA: { certs: [corp] }             # names → HOUBA_TRANSFORM_CA_CERTS
        - rewritePackageSources: { mirror: corp }  # name → HOUBA_TRANSFORM_PACKAGE_MIRRORS
      destinations:
        - project: hardened
          repository: redis
```

Run it: `uv run houba reconcile docs/examples/hardened` — needs `buildctl` on `PATH`, `HOUBA_TRANSFORM_CA_CERTS`, and `HOUBA_TRANSFORM_PACKAGE_MIRRORS` set.
