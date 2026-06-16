# Admission: require a fresh houba scan

The consumer side of the [scan attestation](../../explanation/attestations.md). houba *produces* a
signed scan attestation (predicate `https://houba.dev/predicate/scan/v1`) carrying `attested_at` —
the timestamp it attached and signed the scan. An admission controller *enforces* a **max-age**
against that field: admit an image only if it was scanned recently enough.

This is the freshness half of the [houba / Dependency-Track boundary](../../architecture/decisions/0032-attach-is-scan-provenance-not-a-store.md):
the gate is **purely temporal** (age of a timestamp), never vulnerability correlation. "Is it
vulnerable *today*?" stays Dependency-Track's question; "was it scanned recently and through the
front door?" is what this policy answers.

## Precondition

The signed predicate exists **only when `HOUBA_ATTEST_SIGNER` is set** (`keyless` | `kms` | `key`) on
the `houba attach` run. Without a signer there is no signed attestation, so admission has nothing
trustworthy to gate on. The policy verifies the **signed** `attested_at`, never the unsigned
`io.houba.scan.timestamp` annotation (which exists only for `houba gc`).

## The policy

[`require-fresh-houba-scan.yaml`](require-fresh-houba-scan.yaml) is a Kyverno `ClusterPolicy` that,
for Pods pulling from the front-door registry, requires a houba-signed scan attestation whose
`attested_at` is within 30 days. Adapt three things to your environment:

1. `imageReferences` — your front-door registry glob.
2. `publicKeys` — houba's cosign public key.
3. The `-720h` window — your max-age — and the **Kyverno time expression itself**: validate it against
   your Kyverno version (how predicate fields are referenced, and whether `time_add` accepts a negative
   duration, both vary by version). See
   [Kyverno JMESPath time filters](https://kyverno.io/docs/writing-policies/jmespath/).

Re-attaching an old report resets `attested_at`, so keep CI honest: always scan-then-attach. houba
does not police that — freshness staleness from re-attach is out of scope (ADR 0032).
