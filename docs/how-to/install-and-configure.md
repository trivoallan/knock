# Install and configure knock

Install knock, configure its registries and run it beyond the README quick start. Moved from the README.

## Install, configure, try

### Install

`knock` is published as a Docker image bundling `regctl`, BuildKit (`buildctl`), and the Python CLI
itself:

```bash
docker pull ghcr.io/<your-org>/knock:<version>   # e.g. 0.13.0
```

(The runtime image also bundles `cosign` for the optional signed attestations.)

The published image is multi-arch (`amd64` + `arm64`) and is signed keyless with `cosign`; it also
carries an SBOM and SLSA provenance attached as buildx attestations. Verify the signature before
running:

```bash
cosign verify ghcr.io/trivoallan/knock:<version> \
  --certificate-identity-regexp '^https://github.com/trivoallan/knock/\.github/workflows/release\.yml@refs/heads/main$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

The `main` tag is rebuilt and signed by the same workflow on every push to `main`, so pin a
version (`X.Y.Z`) or a digest.

The SBOM and provenance are buildx attestations (OCI referrers, not cosign-signed) — inspect them
with `docker buildx imagetools inspect`:

```bash
docker buildx imagetools inspect ghcr.io/trivoallan/knock:<version> --format '{{ json .SBOM }}'
docker buildx imagetools inspect ghcr.io/trivoallan/knock:<version> --format '{{ json .Provenance }}'
```

Or from source with [uv](https://github.com/astral-sh/uv):

```bash
git clone https://github.com/trivoallan/knock.git
cd knock
uv sync
uv run knock --help
```

When running from source you need `regctl` on `PATH` (plus `buildctl` if you use the rebuild path).

### Configuration

`knock` reads its configuration from environment variables (12-factor). All variables are
namespaced `KNOCK_*`. The table below covers the common ones; the exhaustive, always-current
list is the generated [config reference](../reference/configuration.md) (and
[policy reference](../reference/schemas/mirror-policy.md) for `MirrorPolicy` fields).

| Variable | Required | Default | Description |
|---|---|---|---|
| `KNOCK_REGISTRIES` | yes¹ | `{}` | JSON map of logical registry name → `RegistryConfig` (source and destination registries; see below). |
| `KNOCK_LABEL_PREFIX` | no | `io.knock` | Prefix for knock's own provenance annotations (empty ⇒ no knock labels). |
| `KNOCK_BUILD_PLATFORM` | no | `linux/amd64` | Platform of a rebuild whose policy declares no `platforms`. |
| `KNOCK_MAX_CONCURRENCY` | no | `4` | Max parallel tag operations per run (`1` = sequential). Override per run with `--concurrency` / `-j`. |
| `KNOCK_WORK_DIR` | no | `/tmp/knock-work` | Scratch directory for build contexts. |
| `KNOCK_TRANSFORM_CA_CERTS` | no | `{}` | JSON map of name → CA source, resolved by the `injectCA` transform. |
| `KNOCK_TRANSFORM_PACKAGE_MIRRORS` | no | `{}` | JSON map of name → package mirror, resolved by `rewritePackageSources`. |
| `KNOCK_ATTEST_SIGNER` | no | `""` | `""` (off) / `keyless` / `kms` / `key` — enables signed SLSA attestations on the rebuild path. `kms`/`key` also need `KNOCK_ATTEST_KEY_REF`; keyless uses `KNOCK_ATTEST_FULCIO_URL` / `_REKOR_URL`. |
| `KNOCK_PURGE_MIN_IDLE_DAYS` | no | _unset_ | Idle window `knock purge` requires before reaping a marked tag (required to run `purge`). |
| `KNOCK_RETENTION` | no | _unset_ | JSON `Archive` object (`{keep, olderThanDays}`) enabling fleet-wide retention marking during `reconcile`; a policy's `archive:` overrides it per field. Unset ⇒ retention off everywhere. |
| `KNOCK_LOG_FORMAT` | no | `text` | `text` or `json`. |
| `KNOCK_LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `KNOCK_DRY_RUN_TAGS` | no | `false` | Skip image copies / pushes. |
| `KNOCK_DRY_RUN_DELETIONS` | no | `false` | Skip deletions. |

¹ Defaults to empty, but at least one registry must be configured to reconcile anything.

**`RegistryConfig` fields** (each entry in `KNOCK_REGISTRIES`):

| Field | Required | Description |
|---|---|---|
| `host` | yes | Registry host, e.g. `harbor.example.com` or `localhost:5001`. |
| `username` | no | Registry username (must be set together with `password`). |
| `password` | no | Registry password (must be set together with `username`). |
| `tls_verify` | no | Set to `false` for plain-HTTP registries (default `true`); knock runs `regctl registry set … --tls disabled` automatically. |
| `ca_cert` | no | Path to a CA PEM `regctl` should trust for this registry's TLS (registries behind an internal CA). |

> The transform rosters are separate, named indirections so policies stay portable and this repo
> stays generic: a policy references `injectCA: {certs: [corp]}` / `rewritePackageSources:
> {mirror: internal}`, and `corp` / `internal` resolve to org-specific data here. A `CACertSource`
> is `{path}` **or** `{pem}`; a package mirror is `{apt}` and/or `{apk}`.

### Try it

[**Getting started**](../tutorials/getting-started.md) runs `knock reconcile` end-to-end against a local
registry in about ten minutes — from an empty registry to an inspectable provenance stamp. From
there, [`docs/examples/`](../reference/examples/README.md) is a catalog of runnable `MirrorPolicy` files,
one per capability: select redis by semver, rebuild Debian into per-region timezone variants,
retention, delegated deletion, scan ingestion. Every `reconcile` is **plan-then-apply** — pass
`--dry-run` to see the plan first.
