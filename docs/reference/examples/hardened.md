---
title: "Hardened rebuild"
description: "Rebuild path with org hardening: inject internal CA, rewrite package sources."
sidebar_position: 3
---

The rebuild path with org hardening: inject internal CA certs (`injectCA`) and rewrite package sources to an internal mirror (`rewritePackageSources`), then stamp the result. The transform engine is implemented; running it needs a BuildKit daemon (`buildctl`) plus org-specific config (`KNOCK_TRANSFORM_CA_CERTS` / `KNOCK_TRANSFORM_PACKAGE_MIRRORS`). See [Transforms & signed attestations](../../explanation/attestations.md) for the full walkthrough.

```yaml title="docs/examples/hardened/redis.yml" file=../../examples/hardened/redis.yml
```

Run it: `uv run knock reconcile docs/examples/hardened` — needs `buildctl` on `PATH`, `KNOCK_TRANSFORM_CA_CERTS`, and `KNOCK_TRANSFORM_PACKAGE_MIRRORS` set.
