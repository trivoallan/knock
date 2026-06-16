# houba

**The single front door for the external container images your organization runs.**

> **Status — young but functional (`v0.6`).** Delivered: the full hexagon; both the copy and the
> rebuild / derive-and-stamp paths; the pluggable transform engine; the OCI provenance stamp **plus
> signed SLSA / in-toto attestations** (rebuild *and* ingested scan results); the
> `reconcile` / `purge` / `attach` / `audit` / `gc` commands; retention-driven soft-delete; concurrent +
> shardable reconcile; and optional KEDA autoscaling of the build path. The single-front-door mandate
> is **enforceable** (`attach --fail-on`, `audit --fail-on-uncovered`) and **trustworthy**
> (`audit --signed`), and the provenance contract is frozen. Next: publishing the user docs site
> ([roadmap](docs/roadmap.md)). Not yet battle-hardened for production.

Every public image that enters your registry passes through houba: it is mirrored — or, when you
declare a hardening policy, rebuilt with internal CA certificates and internal package mirrors —
and stamped with **standardized, portable provenance** (OCI annotations plus signed SLSA / in-toto
attestations).

The payoff lands the morning a critical CVE drops. Because every image that came in through houba
carries a consistent provenance stamp, *"what's our blast radius, and who owns it?"* becomes **one
query** in the observability stack you already have — not a frantic spreadsheet. houba produces the
stamp; your tools (Datadog, PowerBI, Wiz…) read it.

houba is **not** an image mirror. `skopeo sync` and Harbor replication copy images byte-for-byte.
houba *stamps* every image with portable provenance — and *hardens* the ones you choose to rebuild.

**New here?** Read [Why houba](docs/index.md) for the case, then [Getting started](docs/tutorials/getting-started.md)
to mirror your first image and inspect its stamp in ten minutes.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org)

---

## How it works

For each image you bring in, you declare a small `MirrorPolicy` (source, tag-selection rules,
optional hardening steps). `houba reconcile` then, per policy:

1. Lists tags on the source registry (via `regctl`).
2. Selects which tags to import — regex include/exclude filters, semver ordering, moving-tag
   aliases, and a 7-day stability window for moving digests.
3. For each tag: **mirrors** it as-is (`regctl copy`), or — when the policy declares a `transform`
   — **rebuilds** it through BuildKit (`buildctl`) with your hardening steps (internal CAs,
   internal package mirrors, timezone, …).
4. **Stamps** the result with standardized provenance — OCI-standard annotations plus an
   `io.houba.*` transformation lineage, and (when configured) a signed SLSA / in-toto attestation.
5. Pushes to your registry, updates the moving-tag aliases, and archives superseded tags.
6. Reports the run — a human/JSON report to stdout, a structured event journal to stderr — and
   exits with a code reflecting the worst policy outcome.

Change detection is provenance-based and idempotent: re-running `reconcile` is a no-op unless the
source digest moved (past the stability window) or you changed the hardening.

`reconcile` also enforces **retention**: when a policy (or the fleet-wide `HOUBA_RETENTION`) sets
`archive: {keep, olderThanDays}`, houba keeps the N most-recently-imported tags of each stream and
attaches a `pending-deletion` mark (reason `retention-excess`) to the older surplus — reaching the
*valid, in-selection* tags that selection filtering structurally never would. Retention only ever
**marks** (it never hard-deletes, even under `deletionMode: purge`), so removal always passes through
the usage-gated reaper below.

Beyond `reconcile`, the CLI offers:

- **`houba audit`** — a coverage-gap report: walk the registry and list images that do **not** carry
  houba's stamp (`--fail-on-uncovered` makes it a CI gate); `--signed` adds a *signed*-vs-merely-stamped
  tier (`--fail-on-unsigned`). This is what makes the front door *verifiable* and *trustworthy*.
- **`houba purge`** — the reference reaper: hard-delete tags marked `pending-deletion` (by either
  the selection axis or retention) that a usage oracle confirms are unused (gated by
  `HOUBA_PURGE_MIN_IDLE_DAYS`; dry-run unless `--apply`).
- **`houba attach <ref> --report <file>`** — ingest an upstream scan report (e.g. SARIF) and attach
  it as a stamped OCI referrer on the image — additionally **signed** as an in-toto scan attestation
  when `HOUBA_ATTEST_SIGNER` is set, turning "this image was scanned" into a verifiable fact.
  `--fail-on <severity>` doubles it as a CI gate.
- **`houba gc`** — garbage-collect superseded scan-result referrers: keep the newest per
  `(tool, format)` and collect the rest (`--keep` / `--older-than-days`; dry-run unless `--apply`),
  so `attach` volume doesn't pile up over time.

See the [roadmap](docs/roadmap.md) for what is built versus planned, and the
[design overview](docs/architecture/design.md) for the architecture.

### Run it as a deployment

A **reference deployment** runs houba as a Kubernetes CronJob (git-sync'd policies, rootless
buildkitd, a blast-radius consumer) — the same `deploy/` manifests serve a local kind demo and a
production blueprint. Fastest taste:

```bash
make demo             # kind up, sync the Argo reference, reconcile the example, print blast radius
```

See [docs/how-to/reference-deployment.md](docs/how-to/reference-deployment.md).

---

## Quick start

### Install

`houba` is published as a Docker image bundling `regctl`, BuildKit (`buildctl`), and the Python CLI
itself:

```bash
docker pull ghcr.io/<your-org>/houba:0.6
```

(The runtime image also bundles `cosign` for the optional signed attestations.)

The published image is multi-arch (`amd64` + `arm64`) and is signed keyless with `cosign`; it also
carries an SBOM and SLSA provenance attached as buildx attestations. Verify the signature before
running:

```bash
cosign verify ghcr.io/trivoallan/houba:0.6 \
  --certificate-identity-regexp 'https://github.com/trivoallan/houba/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

The SBOM and provenance are buildx attestations (OCI referrers, not cosign-signed) — inspect them
with `docker buildx imagetools inspect`:

```bash
docker buildx imagetools inspect ghcr.io/trivoallan/houba:0.6 --format '{{ json .SBOM }}'
docker buildx imagetools inspect ghcr.io/trivoallan/houba:0.6 --format '{{ json .Provenance }}'
```

Or from source with [uv](https://github.com/astral-sh/uv):

```bash
git clone https://github.com/trivoallan/houba.git
cd houba
uv sync
uv run houba --help
```

When running from source you need `regctl` on `PATH` (plus `buildctl` if you use the rebuild path).

### Configuration

`houba` reads its configuration from environment variables (12-factor). All variables are
namespaced `HOUBA_*`. The table below covers the common ones; the exhaustive, always-current
list is the generated [config reference](docs/reference/config.md) (and
[policy reference](docs/reference/mirror-policy.md) for `MirrorPolicy` fields).

| Variable | Required | Default | Description |
|---|---|---|---|
| `HOUBA_REGISTRIES` | yes¹ | `{}` | JSON map of logical registry name → `RegistryConfig` (source and destination registries; see below). |
| `HOUBA_LABEL_PREFIX` | no | `io.houba` | Prefix for houba's own provenance annotations (empty ⇒ no houba labels). |
| `HOUBA_BUILD_PLATFORM` | no | `linux/amd64` | Platform for the rebuild path (single-platform). |
| `HOUBA_MAX_CONCURRENCY` | no | `4` | Max parallel tag operations per run (`1` = sequential). Override per run with `--concurrency` / `-j`. |
| `HOUBA_WORK_DIR` | no | `/tmp/houba-work` | Scratch directory for build contexts. |
| `HOUBA_TRANSFORM_CA_CERTS` | no | `{}` | JSON map of name → CA source, resolved by the `injectCA` transform. |
| `HOUBA_TRANSFORM_PACKAGE_MIRRORS` | no | `{}` | JSON map of name → package mirror, resolved by `rewritePackageSources`. |
| `HOUBA_ATTEST_SIGNER` | no | `""` | `""` (off) / `keyless` / `kms` / `key` — enables signed SLSA attestations on the rebuild path. `kms`/`key` also need `HOUBA_ATTEST_KEY_REF`; keyless uses `HOUBA_ATTEST_FULCIO_URL` / `_REKOR_URL`. |
| `HOUBA_PURGE_MIN_IDLE_DAYS` | no | _unset_ | Idle window `houba purge` requires before reaping a marked tag (required to run `purge`). |
| `HOUBA_RETENTION` | no | _unset_ | JSON `Archive` object (`{keep, olderThanDays}`) enabling fleet-wide retention marking during `reconcile`; a policy's `archive:` overrides it per field. Unset ⇒ retention off everywhere. |
| `HOUBA_LOG_FORMAT` | no | `text` | `text` or `json`. |
| `HOUBA_LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `HOUBA_DRY_RUN_TAGS` | no | `false` | Skip image copies / pushes. |
| `HOUBA_DRY_RUN_DELETIONS` | no | `false` | Skip deletions. |

¹ Defaults to empty, but at least one registry must be configured to reconcile anything.

**`RegistryConfig` fields** (each entry in `HOUBA_REGISTRIES`):

| Field | Required | Description |
|---|---|---|
| `host` | yes | Registry host, e.g. `harbor.example.com` or `localhost:5001`. |
| `username` | no | Registry username (must be set together with `password`). |
| `password` | no | Registry password (must be set together with `username`). |
| `tls_verify` | no | Set to `false` for plain-HTTP registries (default `true`); houba runs `regctl registry set … --tls disabled` automatically. |
| `ca_cert` | no | Path to a CA PEM `regctl` should trust for this registry's TLS (registries behind an internal CA). |

> The transform rosters are separate, named indirections so policies stay portable and this repo
> stays generic: a policy references `injectCA: {certs: [corp]}` / `rewritePackageSources:
> {mirror: internal}`, and `corp` / `internal` resolve to org-specific data here. A `CACertSource`
> is `{path}` **or** `{pem}`; a package mirror is `{apt}` and/or `{apk}`.

### Try it

[**Getting started**](docs/tutorials/getting-started.md) runs `houba reconcile` end-to-end against a local
registry in about ten minutes — from an empty registry to an inspectable provenance stamp. From
there, [`docs/examples/`](docs/examples/README.md) is a catalog of runnable `MirrorPolicy` files,
one per capability: select redis by semver, rebuild Debian into per-region timezone variants,
retention, delegated deletion, scan ingestion. Every `reconcile` is **plan-then-apply** — pass
`--dry-run` to see the plan first.

---

## Architecture

`houba` follows hexagonal architecture (ports & adapters):

```
houba/
├── domain/      pure logic — mirror_policy, selection, aliases, semver, expand, policy_merge,
│                variants, reconcile, collision, sharding, stamp, attestation, coverage,
│                lifecycle, retention, purge, scan/, transforms/
├── ports/       typing.Protocol interfaces — registry, image_builder, attestor,
│                usage_oracle, reporter, clock
├── adapters/    concrete I/O — regctl_cli, buildkit_cli, cosign_cli, command_usage,
│                structlog_reporter, system_clock
├── use_cases/   orchestration — loader, reconcile, purge, attach, audit, gc, report
└── cli/         Typer entry points — reconcile, purge, attach, audit, gc, version
```

**Golden rules**

- `domain/` never imports I/O (no `httpx`, no `subprocess`, no `os.environ`, no clock).
- `use_cases/` receive ports by injection; they never import adapters.
- `cli/` parses arguments and maps exceptions to exit codes; everything else is delegated.
- Environment variables are read only inside `houba/config.py`.

The current adapters all shell out via `subprocess` (`regctl`, `buildctl`) or use the stdlib —
there is no HTTP client. This keeps the business logic 100 % unit-testable with in-memory fakes
(`tests/fakes/*`), and the adapters integration-testable in isolation with fake-bin shell scripts.
The full picture — and the C4 model — is in [`docs/architecture/`](docs/architecture/design.md).

---

## Development

```bash
uv sync                                                        # install deps
uv run pytest                                                  # full suite
uv run pytest tests/unit/domain --cov=houba.domain --cov-fail-under=90
uv run ruff check . && uv run ruff format --check .
uv run mypy houba
docker build -t houba:dev .                                    # build the runtime image
```

Coverage gates enforced in CI: **≥ 80 % global**, **≥ 90 % on `houba.domain`**.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

Copyright 2026 Tristan Rivoallan and contributors.
