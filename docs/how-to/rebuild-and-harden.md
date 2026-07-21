---
title: "Rebuild & harden an image"
description: "Place an image through the rebuild path: inject internal CA certs, rewrite package sources to an internal mirror, stamp the result, and optionally sign it."
sidebar_position: 1
---

A policy with **no** `transform` is copied byte-for-byte and stamped (see
[Getting started](../tutorials/getting-started.md)). Add a `transform` and knock switches to the
**rebuild path**: it rebuilds the image through BuildKit applying declarative hardening primitives,
then stamps the result with `base.digest` = the source digest plus `io.knock.transform.*` lineage.
The policy stays portable — it only *names* the CA(s) and mirror; the org-specific data lives in
configuration. For the concepts behind this, see
[Transforms & signed attestations](../explanation/attestations.md).

## 1. Declare the transform in the policy

The [`hardened/redis.yml`](../examples/hardened/redis.yml) example injects an internal CA and
rewrites package sources to an internal mirror:

```yaml
imports:
  - name: v7
    owners:
      - group:default/data-platform        # stamped as io.knock.owners
    tags:
      includeRegex: "^7\.2\."
    transform:
      - injectCA: { certs: [corp] }              # names → KNOCK_TRANSFORM_CA_CERTS
      - rewritePackageSources: { mirror: corp }  # name → KNOCK_TRANSFORM_PACKAGE_MIRRORS
    destinations:
      - project: hardened
        repository: redis
```

## 2. Supply the org-specific config

The policy only names `corp`; the actual cert path and mirror URLs are configuration, so the same
policy is portable across orgs:

```bash
export KNOCK_TRANSFORM_CA_CERTS='{"corp": {"path": "/etc/knock/certs/corp-root.pem"}}'
export KNOCK_TRANSFORM_PACKAGE_MIRRORS='{"corp": {"apt": "https://mirror.corp/debian", "apk": "https://mirror.corp/alpine"}}'
```

## 3. Reconcile (rebuild)

```bash
knock reconcile docs/examples/hardened
# rebuilt docker.io/library/redis:7.2.x → hardened/redis:7.2.x
#   base.digest=sha256:src…  transform=injectCA,rewritePackageSources
```

:::note
`buildctl` must be on `PATH` (the runtime image bundles it). Without a `transform`, this same command would copy instead of rebuild.
:::

## 4. Inspect the stamp

```bash
regctl image config registry.example.com/hardened/redis:7.2.0 \
  | jq '.config.Labels | with_entries(select(.key | startswith("io.knock")))'
# io.knock.transform.steps  = "injectCA,rewritePackageSources"
# io.knock.owners           = "group:default/data-platform"
```

## 5. Sign the rebuild (verifiable provenance)

[`attested/redis.yml`](../examples/attested/redis.yml) is the same rebuild with signing on. Signing
is org configuration, not policy — the file stays portable:

```bash
export KNOCK_ATTEST_SIGNER=keyless                       # or: kms | key
export KNOCK_ATTEST_BUILDER_ID=https://knock.example/builders/main
# keyless: optional internal CA + transparency log (blank rekor => no log entry)
export KNOCK_ATTEST_FULCIO_URL=https://fulcio.corp

knock reconcile docs/examples/attested
# rebuilt … → attested/redis:7.2.x
#   signed: https://knock.dev/predicate/transform/v1 → sha256:att…
#   signed: https://slsa.dev/provenance/v1 (buildkit) → sha256:att…
```

:::note
`cosign` must be on `PATH`. Off by default: with no `KNOCK_ATTEST_SIGNER`, the rebuild is stamped but unsigned.
:::

To verify the result and the attached SBOM, see
[Inspect an image's SBOM](inspect-sbom.md). For every signer knob, see the
[configuration reference](../reference/configuration.md).
