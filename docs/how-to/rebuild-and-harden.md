# Rebuild & harden an image

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

> [!NOTE]
> `buildctl` must be on `PATH` (the runtime image bundles it). Without a `transform`, this same command would copy instead of rebuild.

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

> [!NOTE]
> `cosign` must be on `PATH`. Off by default: with no `KNOCK_ATTEST_SIGNER`, the rebuild is stamped but unsigned.

## 6. Rebuild for several platforms

A rebuild builds `KNOCK_BUILD_PLATFORM` (default `linux/amd64`) unless the policy lists
`platforms`. List them to get one OCI index carrying every platform, in the order given —
[`hardened/python-multiarch.yml`](../examples/hardened/python-multiarch.yml):

```yaml
  imports:
    - name: alpine
      platforms: [linux/amd64, linux/arm64]
      transform:
        - rewritePackageSources: { mirror: corp }
      remediate:
        - upgradePackages: {}
```

The BuildKit host must run the foreign platforms. Register QEMU emulators once per host before
`buildkitd` builds:

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64
```

On GitHub Actions, add `docker/setup-qemu-action` before starting `buildkitd`. Emulated builds
are several times slower; native arm64 BuildKit workers avoid that cost.

What to expect:

- A source tag that lacks a listed platform is refused before any build, with the missing
  platforms named (exit 1); knock never places a smaller index than the policy asked for.
- Adding a platform to a policy rebuilds its placed tags on the next run; upgrading knock alone
  rebuilds nothing.
- The stamp, the transform attestation and the signature are on the index digest; one SBOM per
  format and platform hangs off the index, annotated `io.knock.sbom.platform`.
- A missing emulator fails that tag with a `BuildkitError` (`exec format error`, exit 2).

To verify the result and the attached SBOM, see
[Inspect an image's SBOM](inspect-sbom.md). For every signer knob, see the
[configuration reference](../reference/configuration.md).
