---
sidebar_position: 2
---

# Configuration (HOUBA_*)

Each field is set as `HOUBA_<FIELD>` (the property name upper-cased). JSON-typed fields (`registries`, `transform_ca_certs`, `transform_package_mirrors`, `retention`) take a JSON value whose shape is documented in the [schemas](schemas/) section. The machine-readable contract is [`config.schema.json`](config.schema.json).

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `HOUBA_LABEL_PREFIX` | string | `io.houba` | Prefix for houba's own provenance annotations; empty ⇒ no houba labels (OCI-standard keys only). |
| `HOUBA_REGISTRIES` | JSON object | `{}` | JSON map of logical registry name → `RegistryConfig`. At least one is needed to reconcile. |
| `HOUBA_LOG_FORMAT` | string | `text` | Log output format: `text` or `json`. |
| `HOUBA_LOG_LEVEL` | string | `INFO` | Minimum log level. |
| `HOUBA_DRY_RUN_TAGS` | boolean | `false` | Skip image copies / pushes. |
| `HOUBA_DRY_RUN_DELETIONS` | boolean | `false` | Skip deletions. |
| `HOUBA_DELETION_MODE` | string | `purge` | Global baseline of the deletion-mode cascade. |
| `HOUBA_RETENTION` | JSON object | `(unset)` | Global tier of the retention cascade (a JSON `Archive`); unset ⇒ retention off everywhere. |
| `HOUBA_WORK_DIR` | string | `/tmp/houba-work` | Scratch directory for build contexts. |
| `HOUBA_TRANSFORM_CA_CERTS` | JSON object | `{}` | JSON map of name → CA source, resolved by the `injectCA` transform. |
| `HOUBA_TRANSFORM_PACKAGE_MIRRORS` | JSON object | `{}` | JSON map of name → package mirror, resolved by `rewritePackageSources`. |
| `HOUBA_BUILD_PLATFORM` | string | `linux/amd64` | Platform for the rebuild path (single-platform). |
| `HOUBA_SBOM_FORMATS` | JSON list | `["spdx-json"]` | SBOM formats syft emits on every placed image (copy and rebuild), as a JSON list. Allowed: spdx-json, cyclonedx-json. Non-empty — the knob chooses which formats, never whether (always-on coverage). |
| `HOUBA_MAX_CONCURRENCY` | integer | `4` | Max parallel tag operations per run (`1` = sequential). |
| `HOUBA_ATTEST_SIGNER` | string | `(empty)` | Signing mode for SLSA attestations on the rebuild path; empty ⇒ off. |
| `HOUBA_ATTEST_KEY_REF` | string | `(empty)` | KMS URI (`kms`) or key path (`key`). |
| `HOUBA_ATTEST_FULCIO_URL` | string | `(empty)` | Keyless CA URL; blank ⇒ public Fulcio. |
| `HOUBA_ATTEST_REKOR_URL` | string | `(empty)` | Transparency-log URL; blank ⇒ no log entry. |
| `HOUBA_ATTEST_BUILDER_ID` | string | `(empty)` | URI identifying this houba builder. |
| `HOUBA_USAGE_ORACLE_CMD` | string | `(unset)` | Executable speaking the usage-oracle contract; required to run `houba purge`. |
| `HOUBA_USAGE_ORACLE_TIMEOUT` | integer | `30` | Per-query timeout (seconds) for the usage oracle. |
| `HOUBA_PURGE_MIN_IDLE_DAYS` | integer | `(unset)` | Idle window `houba purge` requires before reaping a marked tag. |
