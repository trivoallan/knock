# Attested rebuild

The same hardening rebuild as [`hardened/`](hardened.md), but with attestation enabled: the output carries two signed in-toto attestations — BuildKit's `slsa.dev/provenance/v1` and knock's `https://knock.dev/predicate/transform/v1` — attached as OCI referrers to the digest. See [Transforms & signed attestations](../../explanation/attestations.md) for the full walkthrough, and [Rebuild and harden](../../how-to/rebuild-and-harden.md) for step-by-step instructions.

[`docs/examples/attested/redis.yml`](../../examples/attested/redis.yml)

Run it: `uv run knock reconcile docs/examples/attested` — needs `buildctl` + `cosign` on `PATH`, `KNOCK_ATTEST_SIGNER` set, and the rebuild config from the [hardened example](hardened.md).
