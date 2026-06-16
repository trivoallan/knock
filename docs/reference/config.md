---
sidebar_position: 2
---

# houba configuration (HOUBA_*)

- [1. Property `houba configuration (HOUBA_*) > label_prefix`](#label_prefix)
- [2. Property `houba configuration (HOUBA_*) > registries`](#registries)
  - [2.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig`](#registries_additionalProperties)
    - [2.1.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > host`](#registries_additionalProperties_host)
    - [2.1.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > username`](#registries_additionalProperties_username)
      - [2.1.2.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > username > anyOf > item 0`](#registries_additionalProperties_username_anyOf_i0)
      - [2.1.2.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > username > anyOf > item 1`](#registries_additionalProperties_username_anyOf_i1)
    - [2.1.3. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > password`](#registries_additionalProperties_password)
      - [2.1.3.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > password > anyOf > item 0`](#registries_additionalProperties_password_anyOf_i0)
      - [2.1.3.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > password > anyOf > item 1`](#registries_additionalProperties_password_anyOf_i1)
    - [2.1.4. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > tls_verify`](#registries_additionalProperties_tls_verify)
    - [2.1.5. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > ca_cert`](#registries_additionalProperties_ca_cert)
      - [2.1.5.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > ca_cert > anyOf > item 0`](#registries_additionalProperties_ca_cert_anyOf_i0)
      - [2.1.5.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > ca_cert > anyOf > item 1`](#registries_additionalProperties_ca_cert_anyOf_i1)
    - [2.1.6. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > deletion_mode`](#registries_additionalProperties_deletion_mode)
      - [2.1.6.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > deletion_mode > anyOf > DeletionMode`](#registries_additionalProperties_deletion_mode_anyOf_i0)
      - [2.1.6.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > deletion_mode > anyOf > item 1`](#registries_additionalProperties_deletion_mode_anyOf_i1)
- [3. Property `houba configuration (HOUBA_*) > log_format`](#log_format)
- [4. Property `houba configuration (HOUBA_*) > log_level`](#log_level)
- [5. Property `houba configuration (HOUBA_*) > dry_run_tags`](#dry_run_tags)
- [6. Property `houba configuration (HOUBA_*) > dry_run_deletions`](#dry_run_deletions)
- [7. Property `houba configuration (HOUBA_*) > deletion_mode`](#deletion_mode)
- [8. Property `houba configuration (HOUBA_*) > retention`](#retention)
  - [8.1. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive`](#retention_anyOf_i0)
    - [8.1.1. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > keep`](#retention_anyOf_i0_keep)
      - [8.1.1.1. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > keep > anyOf > item 0`](#retention_anyOf_i0_keep_anyOf_i0)
      - [8.1.1.2. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > keep > anyOf > item 1`](#retention_anyOf_i0_keep_anyOf_i1)
    - [8.1.2. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > olderThanDays`](#retention_anyOf_i0_olderThanDays)
      - [8.1.2.1. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > olderThanDays > anyOf > item 0`](#retention_anyOf_i0_olderThanDays_anyOf_i0)
      - [8.1.2.2. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > olderThanDays > anyOf > item 1`](#retention_anyOf_i0_olderThanDays_anyOf_i1)
  - [8.2. Property `houba configuration (HOUBA_*) > retention > anyOf > item 1`](#retention_anyOf_i1)
- [9. Property `houba configuration (HOUBA_*) > work_dir`](#work_dir)
- [10. Property `houba configuration (HOUBA_*) > transform_ca_certs`](#transform_ca_certs)
  - [10.1. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource`](#transform_ca_certs_additionalProperties)
    - [10.1.1. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > path`](#transform_ca_certs_additionalProperties_path)
      - [10.1.1.1. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > path > anyOf > item 0`](#transform_ca_certs_additionalProperties_path_anyOf_i0)
      - [10.1.1.2. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > path > anyOf > item 1`](#transform_ca_certs_additionalProperties_path_anyOf_i1)
    - [10.1.2. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > pem`](#transform_ca_certs_additionalProperties_pem)
      - [10.1.2.1. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > pem > anyOf > item 0`](#transform_ca_certs_additionalProperties_pem_anyOf_i0)
      - [10.1.2.2. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > pem > anyOf > item 1`](#transform_ca_certs_additionalProperties_pem_anyOf_i1)
- [11. Property `houba configuration (HOUBA_*) > transform_package_mirrors`](#transform_package_mirrors)
  - [11.1. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror`](#transform_package_mirrors_additionalProperties)
    - [11.1.1. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apt`](#transform_package_mirrors_additionalProperties_apt)
      - [11.1.1.1. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apt > anyOf > item 0`](#transform_package_mirrors_additionalProperties_apt_anyOf_i0)
      - [11.1.1.2. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apt > anyOf > item 1`](#transform_package_mirrors_additionalProperties_apt_anyOf_i1)
    - [11.1.2. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apk`](#transform_package_mirrors_additionalProperties_apk)
      - [11.1.2.1. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apk > anyOf > item 0`](#transform_package_mirrors_additionalProperties_apk_anyOf_i0)
      - [11.1.2.2. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apk > anyOf > item 1`](#transform_package_mirrors_additionalProperties_apk_anyOf_i1)
- [12. Property `houba configuration (HOUBA_*) > build_platform`](#build_platform)
- [13. Property `houba configuration (HOUBA_*) > max_concurrency`](#max_concurrency)
- [14. Property `houba configuration (HOUBA_*) > attest_signer`](#attest_signer)
- [15. Property `houba configuration (HOUBA_*) > attest_key_ref`](#attest_key_ref)
- [16. Property `houba configuration (HOUBA_*) > attest_fulcio_url`](#attest_fulcio_url)
- [17. Property `houba configuration (HOUBA_*) > attest_rekor_url`](#attest_rekor_url)
- [18. Property `houba configuration (HOUBA_*) > attest_builder_id`](#attest_builder_id)
- [19. Property `houba configuration (HOUBA_*) > usage_oracle_cmd`](#usage_oracle_cmd)
  - [19.1. Property `houba configuration (HOUBA_*) > usage_oracle_cmd > anyOf > item 0`](#usage_oracle_cmd_anyOf_i0)
  - [19.2. Property `houba configuration (HOUBA_*) > usage_oracle_cmd > anyOf > item 1`](#usage_oracle_cmd_anyOf_i1)
- [20. Property `houba configuration (HOUBA_*) > usage_oracle_timeout`](#usage_oracle_timeout)
- [21. Property `houba configuration (HOUBA_*) > purge_min_idle_days`](#purge_min_idle_days)
  - [21.1. Property `houba configuration (HOUBA_*) > purge_min_idle_days > anyOf > item 0`](#purge_min_idle_days_anyOf_i0)
  - [21.2. Property `houba configuration (HOUBA_*) > purge_min_idle_days > anyOf > item 1`](#purge_min_idle_days_anyOf_i1)

**Title:** houba configuration (HOUBA_*)

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `object`         |
| **Required**              | No               |
| **Additional properties** | Any type allowed |

| Property                                                   | Pattern | Type             | Deprecated | Definition              | Title/Description                                                                            |
| ---------------------------------------------------------- | ------- | ---------------- | ---------- | ----------------------- | -------------------------------------------------------------------------------------------- |
| - [label_prefix](#label_prefix )                           | No      | string           | No         | -                       | Label Prefix                                                                                 |
| - [registries](#registries )                               | No      | object           | No         | -                       | Registries                                                                                   |
| - [log_format](#log_format )                               | No      | enum (of string) | No         | -                       | Log Format                                                                                   |
| - [log_level](#log_level )                                 | No      | enum (of string) | No         | -                       | Log Level                                                                                    |
| - [dry_run_tags](#dry_run_tags )                           | No      | boolean          | No         | -                       | Dry Run Tags                                                                                 |
| - [dry_run_deletions](#dry_run_deletions )                 | No      | boolean          | No         | -                       | Dry Run Deletions                                                                            |
| - [deletion_mode](#deletion_mode )                         | No      | enum (of string) | No         | In #/$defs/DeletionMode | DeletionMode                                                                                 |
| - [retention](#retention )                                 | No      | Combination      | No         | -                       | Global tier of the retention cascade (a JSON \`Archive\`); unset ⇒ retention off everywhere. |
| - [work_dir](#work_dir )                                   | No      | string           | No         | -                       | Work Dir                                                                                     |
| - [transform_ca_certs](#transform_ca_certs )               | No      | object           | No         | -                       | Transform Ca Certs                                                                           |
| - [transform_package_mirrors](#transform_package_mirrors ) | No      | object           | No         | -                       | Transform Package Mirrors                                                                    |
| - [build_platform](#build_platform )                       | No      | string           | No         | -                       | Build Platform                                                                               |
| - [max_concurrency](#max_concurrency )                     | No      | integer          | No         | -                       | Max Concurrency                                                                              |
| - [attest_signer](#attest_signer )                         | No      | enum (of string) | No         | -                       | Attest Signer                                                                                |
| - [attest_key_ref](#attest_key_ref )                       | No      | string           | No         | -                       | Attest Key Ref                                                                               |
| - [attest_fulcio_url](#attest_fulcio_url )                 | No      | string           | No         | -                       | Attest Fulcio Url                                                                            |
| - [attest_rekor_url](#attest_rekor_url )                   | No      | string           | No         | -                       | Attest Rekor Url                                                                             |
| - [attest_builder_id](#attest_builder_id )                 | No      | string           | No         | -                       | Attest Builder Id                                                                            |
| - [usage_oracle_cmd](#usage_oracle_cmd )                   | No      | Combination      | No         | -                       | Usage Oracle Cmd                                                                             |
| - [usage_oracle_timeout](#usage_oracle_timeout )           | No      | integer          | No         | -                       | Usage Oracle Timeout                                                                         |
| - [purge_min_idle_days](#purge_min_idle_days )             | No      | Combination      | No         | -                       | Purge Min Idle Days                                                                          |

## 1. Property `houba configuration (HOUBA_*) > label_prefix` {#label_prefix}

**Title:** Label Prefix

|              |              |
| ------------ | ------------ |
| **Type**     | `string`     |
| **Required** | No           |
| **Default**  | `"io.houba"` |

**Description:** Prefix for houba's own provenance annotations; empty ⇒ no houba labels (OCI-standard keys only).

## 2. Property `houba configuration (HOUBA_*) > registries` {#registries}

**Title:** Registries

|                           |                                                                                         |
| ------------------------- | --------------------------------------------------------------------------------------- |
| **Type**                  | `object`                                                                                |
| **Required**              | No                                                                                      |
| **Additional properties** | [Each additional property must conform to the schema](#registries_additionalProperties) |

**Description:** JSON map of logical registry name → `RegistryConfig`. At least one is needed to reconcile.

| Property                                | Pattern | Type   | Deprecated | Definition                | Title/Description |
| --------------------------------------- | ------- | ------ | ---------- | ------------------------- | ----------------- |
| - [](#registries_additionalProperties ) | No      | object | No         | In #/$defs/RegistryConfig | RegistryConfig    |

### 2.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig` {#registries_additionalProperties}

**Title:** RegistryConfig

|                           |                        |
| ------------------------- | ---------------------- |
| **Type**                  | `object`               |
| **Required**              | No                     |
| **Additional properties** | Not allowed            |
| **Defined in**            | #/$defs/RegistryConfig |

**Description:** One real registry behind a logical destination name (host + credentials).

| Property                                                           | Pattern | Type        | Deprecated | Definition | Title/Description                                                                        |
| ------------------------------------------------------------------ | ------- | ----------- | ---------- | ---------- | ---------------------------------------------------------------------------------------- |
| + [host](#registries_additionalProperties_host )                   | No      | string      | No         | -          | Host                                                                                     |
| - [username](#registries_additionalProperties_username )           | No      | Combination | No         | -          | Username                                                                                 |
| - [password](#registries_additionalProperties_password )           | No      | Combination | No         | -          | Password                                                                                 |
| - [tls_verify](#registries_additionalProperties_tls_verify )       | No      | boolean     | No         | -          | Tls Verify                                                                               |
| - [ca_cert](#registries_additionalProperties_ca_cert )             | No      | Combination | No         | -          | Ca Cert                                                                                  |
| - [deletion_mode](#registries_additionalProperties_deletion_mode ) | No      | Combination | No         | -          | Destination-level override in the deletion-mode cascade (policy ← destination ← global). |

#### 2.1.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > host` {#registries_additionalProperties_host}

**Title:** Host

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** Registry host, e.g. `harbor.example.com` or `localhost:5001`.

#### 2.1.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > username` {#registries_additionalProperties_username}

**Title:** Username

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Registry username (must be set together with `password`).

| Any of(Option)                                               |
| ------------------------------------------------------------ |
| [item 0](#registries_additionalProperties_username_anyOf_i0) |
| [item 1](#registries_additionalProperties_username_anyOf_i1) |

##### 2.1.2.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > username > anyOf > item 0` {#registries_additionalProperties_username_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### 2.1.2.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > username > anyOf > item 1` {#registries_additionalProperties_username_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 2.1.3. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > password` {#registries_additionalProperties_password}

**Title:** Password

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Registry password (must be set together with `username`).

| Any of(Option)                                               |
| ------------------------------------------------------------ |
| [item 0](#registries_additionalProperties_password_anyOf_i0) |
| [item 1](#registries_additionalProperties_password_anyOf_i1) |

##### 2.1.3.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > password > anyOf > item 0` {#registries_additionalProperties_password_anyOf_i0}

|              |            |
| ------------ | ---------- |
| **Type**     | `string`   |
| **Required** | No         |
| **Format**   | `password` |

##### 2.1.3.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > password > anyOf > item 1` {#registries_additionalProperties_password_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 2.1.4. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > tls_verify` {#registries_additionalProperties_tls_verify}

**Title:** Tls Verify

|              |           |
| ------------ | --------- |
| **Type**     | `boolean` |
| **Required** | No        |
| **Default**  | `true`    |

**Description:** Set to `false` for plain-HTTP registries; houba then pushes insecurely on both paths — `regctl registry set … --tls disabled` for copies and `registry.insecure=true` for BuildKit rebuilds.

#### 2.1.5. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > ca_cert` {#registries_additionalProperties_ca_cert}

**Title:** Ca Cert

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Path to a CA PEM regctl should trust for this registry's TLS (registries behind an internal CA).

| Any of(Option)                                              |
| ----------------------------------------------------------- |
| [item 0](#registries_additionalProperties_ca_cert_anyOf_i0) |
| [item 1](#registries_additionalProperties_ca_cert_anyOf_i1) |

##### 2.1.5.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > ca_cert > anyOf > item 0` {#registries_additionalProperties_ca_cert_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### 2.1.5.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > ca_cert > anyOf > item 1` {#registries_additionalProperties_ca_cert_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 2.1.6. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > deletion_mode` {#registries_additionalProperties_deletion_mode}

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Destination-level override in the deletion-mode cascade (policy ← destination ← global).

| Any of(Option)                                                          |
| ----------------------------------------------------------------------- |
| [DeletionMode](#registries_additionalProperties_deletion_mode_anyOf_i0) |
| [item 1](#registries_additionalProperties_deletion_mode_anyOf_i1)       |

##### 2.1.6.1. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > deletion_mode > anyOf > DeletionMode` {#registries_additionalProperties_deletion_mode_anyOf_i0}

**Title:** DeletionMode

|                |                      |
| -------------- | -------------------- |
| **Type**       | `enum (of string)`   |
| **Required**   | No                   |
| **Defined in** | #/$defs/DeletionMode |

Must be one of:
* "purge"
* "mark"

##### 2.1.6.2. Property `houba configuration (HOUBA_*) > registries > RegistryConfig > deletion_mode > anyOf > item 1` {#registries_additionalProperties_deletion_mode_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

## 3. Property `houba configuration (HOUBA_*) > log_format` {#log_format}

**Title:** Log Format

|              |                    |
| ------------ | ------------------ |
| **Type**     | `enum (of string)` |
| **Required** | No                 |
| **Default**  | `"text"`           |

**Description:** Log output format: `text` or `json`.

Must be one of:
* "text"
* "json"

## 4. Property `houba configuration (HOUBA_*) > log_level` {#log_level}

**Title:** Log Level

|              |                    |
| ------------ | ------------------ |
| **Type**     | `enum (of string)` |
| **Required** | No                 |
| **Default**  | `"INFO"`           |

**Description:** Minimum log level.

Must be one of:
* "DEBUG"
* "INFO"
* "WARN"
* "WARNING"
* "ERROR"

## 5. Property `houba configuration (HOUBA_*) > dry_run_tags` {#dry_run_tags}

**Title:** Dry Run Tags

|              |           |
| ------------ | --------- |
| **Type**     | `boolean` |
| **Required** | No        |
| **Default**  | `false`   |

**Description:** Skip image copies / pushes.

## 6. Property `houba configuration (HOUBA_*) > dry_run_deletions` {#dry_run_deletions}

**Title:** Dry Run Deletions

|              |           |
| ------------ | --------- |
| **Type**     | `boolean` |
| **Required** | No        |
| **Default**  | `false`   |

**Description:** Skip deletions.

## 7. Property `houba configuration (HOUBA_*) > deletion_mode` {#deletion_mode}

**Title:** DeletionMode

|                |                      |
| -------------- | -------------------- |
| **Type**       | `enum (of string)`   |
| **Required**   | No                   |
| **Default**    | `"purge"`            |
| **Defined in** | #/$defs/DeletionMode |

**Description:** Global baseline of the deletion-mode cascade.

Must be one of:
* "purge"
* "mark"

## 8. Property `houba configuration (HOUBA_*) > retention` {#retention}

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Global tier of the retention cascade (a JSON `Archive`); unset ⇒ retention off everywhere.

| Any of(Option)                 |
| ------------------------------ |
| [Archive](#retention_anyOf_i0) |
| [item 1](#retention_anyOf_i1)  |

### 8.1. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive` {#retention_anyOf_i0}

**Title:** Archive

|                           |                 |
| ------------------------- | --------------- |
| **Type**                  | `object`        |
| **Required**              | No              |
| **Additional properties** | Not allowed     |
| **Defined in**            | #/$defs/Archive |

| Property                                              | Pattern | Type        | Deprecated | Definition | Title/Description |
| ----------------------------------------------------- | ------- | ----------- | ---------- | ---------- | ----------------- |
| - [keep](#retention_anyOf_i0_keep )                   | No      | Combination | No         | -          | Keep              |
| - [olderThanDays](#retention_anyOf_i0_olderThanDays ) | No      | Combination | No         | -          | Olderthandays     |

#### 8.1.1. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > keep` {#retention_anyOf_i0_keep}

**Title:** Keep

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Retain the N most-recently-imported tags of each stream.

| Any of(Option)                              |
| ------------------------------------------- |
| [item 0](#retention_anyOf_i0_keep_anyOf_i0) |
| [item 1](#retention_anyOf_i0_keep_anyOf_i1) |

##### 8.1.1.1. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > keep > anyOf > item 0` {#retention_anyOf_i0_keep_anyOf_i0}

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |

##### 8.1.1.2. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > keep > anyOf > item 1` {#retention_anyOf_i0_keep_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 8.1.2. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > olderThanDays` {#retention_anyOf_i0_olderThanDays}

**Title:** Olderthandays

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Of the surplus, only mark tags older than this many days (both conditions hold).

| Any of(Option)                                       |
| ---------------------------------------------------- |
| [item 0](#retention_anyOf_i0_olderThanDays_anyOf_i0) |
| [item 1](#retention_anyOf_i0_olderThanDays_anyOf_i1) |

##### 8.1.2.1. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > olderThanDays > anyOf > item 0` {#retention_anyOf_i0_olderThanDays_anyOf_i0}

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |

##### 8.1.2.2. Property `houba configuration (HOUBA_*) > retention > anyOf > Archive > olderThanDays > anyOf > item 1` {#retention_anyOf_i0_olderThanDays_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

### 8.2. Property `houba configuration (HOUBA_*) > retention > anyOf > item 1` {#retention_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

## 9. Property `houba configuration (HOUBA_*) > work_dir` {#work_dir}

**Title:** Work Dir

|              |                     |
| ------------ | ------------------- |
| **Type**     | `string`            |
| **Required** | No                  |
| **Format**   | `path`              |
| **Default**  | `"/tmp/houba-work"` |

**Description:** Scratch directory for build contexts.

## 10. Property `houba configuration (HOUBA_*) > transform_ca_certs` {#transform_ca_certs}

**Title:** Transform Ca Certs

|                           |                                                                                                 |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| **Type**                  | `object`                                                                                        |
| **Required**              | No                                                                                              |
| **Additional properties** | [Each additional property must conform to the schema](#transform_ca_certs_additionalProperties) |

**Description:** JSON map of name → CA source, resolved by the `injectCA` transform.

| Property                                        | Pattern | Type   | Deprecated | Definition              | Title/Description |
| ----------------------------------------------- | ------- | ------ | ---------- | ----------------------- | ----------------- |
| - [](#transform_ca_certs_additionalProperties ) | No      | object | No         | In #/$defs/CACertSource | CACertSource      |

### 10.1. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource` {#transform_ca_certs_additionalProperties}

**Title:** CACertSource

|                           |                      |
| ------------------------- | -------------------- |
| **Type**                  | `object`             |
| **Required**              | No                   |
| **Additional properties** | Not allowed          |
| **Defined in**            | #/$defs/CACertSource |

**Description:** A CA certificate supplied either as a filesystem path or as an inline PEM string.

| Property                                                 | Pattern | Type        | Deprecated | Definition | Title/Description |
| -------------------------------------------------------- | ------- | ----------- | ---------- | ---------- | ----------------- |
| - [path](#transform_ca_certs_additionalProperties_path ) | No      | Combination | No         | -          | Path              |
| - [pem](#transform_ca_certs_additionalProperties_pem )   | No      | Combination | No         | -          | Pem               |

#### 10.1.1. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > path` {#transform_ca_certs_additionalProperties_path}

**Title:** Path

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Filesystem path to the CA certificate (exactly one of `path` | `pem`).

| Any of(Option)                                                   |
| ---------------------------------------------------------------- |
| [item 0](#transform_ca_certs_additionalProperties_path_anyOf_i0) |
| [item 1](#transform_ca_certs_additionalProperties_path_anyOf_i1) |

##### 10.1.1.1. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > path > anyOf > item 0` {#transform_ca_certs_additionalProperties_path_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### 10.1.1.2. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > path > anyOf > item 1` {#transform_ca_certs_additionalProperties_path_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 10.1.2. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > pem` {#transform_ca_certs_additionalProperties_pem}

**Title:** Pem

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Inline CA certificate PEM string (exactly one of `path` | `pem`).

| Any of(Option)                                                  |
| --------------------------------------------------------------- |
| [item 0](#transform_ca_certs_additionalProperties_pem_anyOf_i0) |
| [item 1](#transform_ca_certs_additionalProperties_pem_anyOf_i1) |

##### 10.1.2.1. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > pem > anyOf > item 0` {#transform_ca_certs_additionalProperties_pem_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### 10.1.2.2. Property `houba configuration (HOUBA_*) > transform_ca_certs > CACertSource > pem > anyOf > item 1` {#transform_ca_certs_additionalProperties_pem_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

## 11. Property `houba configuration (HOUBA_*) > transform_package_mirrors` {#transform_package_mirrors}

**Title:** Transform Package Mirrors

|                           |                                                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Type**                  | `object`                                                                                               |
| **Required**              | No                                                                                                     |
| **Additional properties** | [Each additional property must conform to the schema](#transform_package_mirrors_additionalProperties) |

**Description:** JSON map of name → package mirror, resolved by `rewritePackageSources`.

| Property                                               | Pattern | Type   | Deprecated | Definition               | Title/Description |
| ------------------------------------------------------ | ------- | ------ | ---------- | ------------------------ | ----------------- |
| - [](#transform_package_mirrors_additionalProperties ) | No      | object | No         | In #/$defs/PackageMirror | PackageMirror     |

### 11.1. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror` {#transform_package_mirrors_additionalProperties}

**Title:** PackageMirror

|                           |                       |
| ------------------------- | --------------------- |
| **Type**                  | `object`              |
| **Required**              | No                    |
| **Additional properties** | Not allowed           |
| **Defined in**            | #/$defs/PackageMirror |

**Description:** Override URLs for one or more OS package managers during image hardening.

| Property                                                      | Pattern | Type        | Deprecated | Definition | Title/Description |
| ------------------------------------------------------------- | ------- | ----------- | ---------- | ---------- | ----------------- |
| - [apt](#transform_package_mirrors_additionalProperties_apt ) | No      | Combination | No         | -          | Apt               |
| - [apk](#transform_package_mirrors_additionalProperties_apk ) | No      | Combination | No         | -          | Apk               |

#### 11.1.1. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apt` {#transform_package_mirrors_additionalProperties_apt}

**Title:** Apt

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Override URL for the apt package source (at least one of `apt` | `apk`).

| Any of(Option)                                                         |
| ---------------------------------------------------------------------- |
| [item 0](#transform_package_mirrors_additionalProperties_apt_anyOf_i0) |
| [item 1](#transform_package_mirrors_additionalProperties_apt_anyOf_i1) |

##### 11.1.1.1. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apt > anyOf > item 0` {#transform_package_mirrors_additionalProperties_apt_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### 11.1.1.2. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apt > anyOf > item 1` {#transform_package_mirrors_additionalProperties_apt_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 11.1.2. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apk` {#transform_package_mirrors_additionalProperties_apk}

**Title:** Apk

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Override URL for the apk package source (at least one of `apt` | `apk`).

| Any of(Option)                                                         |
| ---------------------------------------------------------------------- |
| [item 0](#transform_package_mirrors_additionalProperties_apk_anyOf_i0) |
| [item 1](#transform_package_mirrors_additionalProperties_apk_anyOf_i1) |

##### 11.1.2.1. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apk > anyOf > item 0` {#transform_package_mirrors_additionalProperties_apk_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### 11.1.2.2. Property `houba configuration (HOUBA_*) > transform_package_mirrors > PackageMirror > apk > anyOf > item 1` {#transform_package_mirrors_additionalProperties_apk_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

## 12. Property `houba configuration (HOUBA_*) > build_platform` {#build_platform}

**Title:** Build Platform

|              |                 |
| ------------ | --------------- |
| **Type**     | `string`        |
| **Required** | No              |
| **Default**  | `"linux/amd64"` |

**Description:** Platform for the rebuild path (single-platform).

## 13. Property `houba configuration (HOUBA_*) > max_concurrency` {#max_concurrency}

**Title:** Max Concurrency

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `4`       |

**Description:** Max parallel tag operations per run (`1` = sequential).

| Restrictions |        |
| ------------ | ------ |
| **Minimum**  | &ge; 1 |

## 14. Property `houba configuration (HOUBA_*) > attest_signer` {#attest_signer}

**Title:** Attest Signer

|              |                    |
| ------------ | ------------------ |
| **Type**     | `enum (of string)` |
| **Required** | No                 |
| **Default**  | `""`               |

**Description:** Signing mode for SLSA attestations on the rebuild path; empty ⇒ off.

Must be one of:
* ""
* "keyless"
* "kms"
* "key"

## 15. Property `houba configuration (HOUBA_*) > attest_key_ref` {#attest_key_ref}

**Title:** Attest Key Ref

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |
| **Default**  | `""`     |

**Description:** KMS URI (`kms`) or key path (`key`).

## 16. Property `houba configuration (HOUBA_*) > attest_fulcio_url` {#attest_fulcio_url}

**Title:** Attest Fulcio Url

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |
| **Default**  | `""`     |

**Description:** Keyless CA URL; blank ⇒ public Fulcio.

## 17. Property `houba configuration (HOUBA_*) > attest_rekor_url` {#attest_rekor_url}

**Title:** Attest Rekor Url

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |
| **Default**  | `""`     |

**Description:** Transparency-log URL; blank ⇒ no log entry.

## 18. Property `houba configuration (HOUBA_*) > attest_builder_id` {#attest_builder_id}

**Title:** Attest Builder Id

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |
| **Default**  | `""`     |

**Description:** URI identifying this houba builder.

## 19. Property `houba configuration (HOUBA_*) > usage_oracle_cmd` {#usage_oracle_cmd}

**Title:** Usage Oracle Cmd

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Executable speaking the usage-oracle contract; required to run `houba purge`.

| Any of(Option)                       |
| ------------------------------------ |
| [item 0](#usage_oracle_cmd_anyOf_i0) |
| [item 1](#usage_oracle_cmd_anyOf_i1) |

### 19.1. Property `houba configuration (HOUBA_*) > usage_oracle_cmd > anyOf > item 0` {#usage_oracle_cmd_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

### 19.2. Property `houba configuration (HOUBA_*) > usage_oracle_cmd > anyOf > item 1` {#usage_oracle_cmd_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

## 20. Property `houba configuration (HOUBA_*) > usage_oracle_timeout` {#usage_oracle_timeout}

**Title:** Usage Oracle Timeout

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `30`      |

**Description:** Per-query timeout (seconds) for the usage oracle.

| Restrictions |        |
| ------------ | ------ |
| **Minimum**  | &ge; 1 |

## 21. Property `houba configuration (HOUBA_*) > purge_min_idle_days` {#purge_min_idle_days}

**Title:** Purge Min Idle Days

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Idle window `houba purge` requires before reaping a marked tag.

| Any of(Option)                          |
| --------------------------------------- |
| [item 0](#purge_min_idle_days_anyOf_i0) |
| [item 1](#purge_min_idle_days_anyOf_i1) |

### 21.1. Property `houba configuration (HOUBA_*) > purge_min_idle_days > anyOf > item 0` {#purge_min_idle_days_anyOf_i0}

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |

| Restrictions |        |
| ------------ | ------ |
| **Minimum**  | &ge; 1 |

### 21.2. Property `houba configuration (HOUBA_*) > purge_min_idle_days > anyOf > item 1` {#purge_min_idle_days_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

----------------------------------------------------------------------------------------------------------------------------
