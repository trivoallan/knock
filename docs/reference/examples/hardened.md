# Hardened rebuild

The rebuild path with org hardening: inject internal CA certs (`injectCA`) and rewrite package sources to an internal mirror (`rewritePackageSources`), then stamp the result. The transform engine is implemented; running it needs a BuildKit daemon (`buildctl`) plus org-specific config (`KNOCK_TRANSFORM_CA_CERTS` / `KNOCK_TRANSFORM_PACKAGE_MIRRORS`). See [Transforms & signed attestations](../../explanation/attestations.md) for the full walkthrough.

[`docs/examples/hardened/redis.yml`](../../examples/hardened/redis.yml)

[`docs/examples/hardened/python-multiarch.yml`](../../examples/hardened/python-multiarch.yml) — the same rebuild path for `linux/amd64` and `linux/arm64` under one index ([ADR 0057](../../architecture/decisions/0057-multi-platform-rebuild.md)); the BuildKit host needs binfmt emulators for the foreign platform.

Run it: `uv run knock reconcile docs/examples/hardened` — needs `buildctl` on `PATH`, `KNOCK_TRANSFORM_CA_CERTS`, and `KNOCK_TRANSFORM_PACKAGE_MIRRORS` set.
