# Example policies

A catalog of runnable `MirrorPolicy` files, each demonstrating one houba capability against a
**local registry**. New to houba? Start with **[Getting started](../tutorials/getting-started.md)** — it
walks the smallest copy-path example (busybox) from an empty registry to an inspectable
provenance stamp in about ten minutes. The examples below build on that same local setup
(`HOUBA_REGISTRIES` roster + a throwaway `registry:2`).

## The examples

**[`reference/`](https://github.com/trivoallan/houba/tree/main/docs/examples/reference)** is **the** policy the reference deployment reconciles — both
`make demo` (the Argo App-of-Apps) and `make local` (the inner-loop overlay) run it — see the
[Reference](https://github.com/trivoallan/houba/blob/main/docs/architecture/_export/structurizr-DeployReference.mmd) and
[Local](https://github.com/trivoallan/houba/blob/main/docs/architecture/_export/structurizr-DeployLocal.mmd) deployment views. One reconcile
demonstrates **copy *and* rebuild** in a single, self-contained pass (no Harbor, no org config):

- **[`reference/busybox/`](https://github.com/trivoallan/houba/blob/main/docs/examples/reference/busybox/busybox.yml)** — the **copy path**: select
  `1.36.x`/`1.37.x`, alias `{major}.{minor}` + `latest`, mirror into `demo/busybox`. The smallest,
  fastest case, and the one [Getting started](../tutorials/getting-started.md) runs.
- **[`reference/debian-tz/`](https://github.com/trivoallan/houba/blob/main/docs/examples/reference/debian-tz/debian-tz.yml)** — the **rebuild path, runnable
  self-contained**: rebuild `debian:bookworm-slim` through `setTimezone` (the one built-in step that
  needs no org config) and fan it into **`-eu` / `-us` variants** via the per-variant `suffix` (the
  worked example of `variants`), stamped into `demo/debian`.

The remaining examples are **standalone feature docs** — each is a `MirrorPolicy` demonstrating one
capability, runnable on its own with `uv run houba …` (not part of the bundled demo):

- **[`redis/redis.yml`](https://github.com/trivoallan/houba/blob/main/docs/examples/redis/redis.yml)** — semver selection over a real image (`7.2.x`),
  showing how aliases track the highest patch per minor (`7.2` → the latest `7.2.z`) and
  `latest` → the highest overall. Larger image, slower to copy:
  `uv run houba reconcile docs/examples/redis`.
- **[`hardened/redis.yml`](https://github.com/trivoallan/houba/blob/main/docs/examples/hardened/redis.yml)** — the **rebuild path with org hardening**: inject
  internal CA certs (`injectCA`) + rewrite package sources to an internal mirror, then stamp the
  result. The transform engine is implemented; running it needs a BuildKit daemon (`buildctl`) plus
  the org's `HOUBA_TRANSFORM_CA_CERTS` / `HOUBA_TRANSFORM_PACKAGE_MIRRORS` config (which is why the
  self-contained demo uses the simpler `setTimezone` rebuild instead). See
  [Transforms & signed attestations](../explanation/attestations.md).
- **[`attested/redis.yml`](https://github.com/trivoallan/houba/blob/main/docs/examples/attested/redis.yml)** — the **rebuild path, signed**: the same
  hardening rebuild as `hardened/`, but with attestation enabled so the output carries two
  in-toto attestations — BuildKit's `slsa.dev/provenance/v1` and houba's
  `https://houba.dev/predicate/transform/v1`. **Requires the attestation path**: set
  `HOUBA_ATTEST_SIGNER` (`keyless` | `kms` | `key`) and a `cosign` on `PATH`; off by default.
  See [Transforms & signed attestations](../explanation/attestations.md).
- **[`pending-deletion/pending-deletion.yml`](https://github.com/trivoallan/houba/blob/main/docs/examples/pending-deletion/pending-deletion.yml)** —
  `deletionMode: mark`: when a tag drops out of the selection, houba attaches a
  `pending-deletion` OCI referrer instead of deleting it. See
  [Deletion & retention](../explanation/deletion-and-retention.md).
- **[`retention/redis.yml`](https://github.com/trivoallan/houba/blob/main/docs/examples/retention/redis.yml)** — **retention-driven soft-delete**: cap
  *valid, in-selection* tags with `archive: {keep, olderThanDays}`. houba keeps the N most-recently
  imported tags of each stream and marks the older surplus `pending-deletion`
  (reason `retention-excess`) for the reaper — the one axis selection filtering can't reach. See
  [Deletion & retention](../explanation/deletion-and-retention.md#retention-capping-valid-tags).
- **[`oracles/datadog.sh`](https://github.com/trivoallan/houba/blob/main/docs/examples/oracles/datadog.sh)** — reference usage oracle for `houba purge`.
  See [Purge unused tags](../how-to/purge-unused-tags.md).
- **[`scan/README.md`](scan/README.md)** — the **`houba attach` path**: ingest an
  upstream SARIF report and stamp it as a portable OCI referrer on the image's digest —
  also signed as an in-toto scan attestation when `HOUBA_ATTEST_SIGNER` is set.
  houba does not run a scanner — the scan is produced upstream (CI, registry-native
  scanner, or scan service) and handed in. `scan/sample.sarif.json` is a runnable
  example report (1 critical CVE, 1 medium).
- **[`scan-gc/README.md`](scan-gc/README.md)** — the **`houba gc` path**: garbage-collect
  superseded scan referrers across the roster, keeping the N newest per `(tool, format)` older
  than a grace window. Dry-run by default; `--apply` to delete. See [ADR 0028](https://github.com/trivoallan/houba/blob/main/docs/architecture/decisions/0028-scan-referrer-gc.md).

## Going deeper

The discursive background and the command walkthroughs for these capabilities now live with the
rest of the docs:

- **How-to** — [Purge unused tags](../how-to/purge-unused-tags.md) · [Audit coverage](../how-to/audit-coverage.md)
- **Explanation** — [Deletion & retention](../explanation/deletion-and-retention.md) · [Transforms & signed attestations](../explanation/attestations.md)

## Notes

**Upgrade note.** The `io.houba.transform.version` hash format changed when the pluggable registry
landed; on the first reconcile after upgrading, already-hardened images rebuild **once** (their
recorded version no longer matches), then stay idempotent.

The copy-path examples keep `registry` off the destinations (resolved to the single
configured `local` registry), so they stay portable — the same policy file works against
any registry roster.

> **One repository per policy.** Each destination repository must be owned by exactly one `MirrorPolicy` —
> two policies writing the same repo is rejected at load time (they would mutually delete each other's
> tags). This is also what makes horizontal sharding safe (one writer per repo).

> A policy is just data. The full field reference is generated from the Pydantic models:
> **[policy reference](../reference/mirror-policy.md)** (human) and
> [`mirror-policy.schema.json`](https://github.com/trivoallan/houba/blob/main/docs/reference/mirror-policy.schema.json) (for editor/CI validation).
> Every `HOUBA_*` variable is likewise documented in the **[config reference](../reference/config.md)**.
