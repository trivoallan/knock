---
title: "Attested rebuild"
description: "Rebuild path with signed in-toto attestations (SLSA + houba transform)."
sidebar_position: 4
---

The same hardening rebuild as [`hardened/`](hardened.md), but with attestation enabled: the output carries two signed in-toto attestations — BuildKit's `slsa.dev/provenance/v1` and houba's `https://houba.dev/predicate/transform/v1` — attached as OCI referrers to the digest. See [Transforms & signed attestations](../../explanation/attestations.md) for the full walkthrough, and [Rebuild and harden](../../how-to/rebuild-and-harden.md) for step-by-step instructions.

```yaml title="docs/examples/attested/redis.yml" file=../../examples/attested/redis.yml
```

Run it: `uv run houba reconcile docs/examples/attested` — needs `buildctl` + `cosign` on `PATH`, `HOUBA_ATTEST_SIGNER` set, and the rebuild config from the [hardened example](hardened.md).
