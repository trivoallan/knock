---
sidebar_position: 4
---

# CoverageReport (knock audit JSON output)

- [1. Property `apiVersion`](#apiVersion)
- [2. Property `kind`](#kind)
- [3. Property `registries`](#registries)
  - [3.1. registries items](#registries_items)
- [4. Property `counts`](#counts)
  - [4.1. Property `scanned`](#counts_scanned)
  - [4.2. Property `covered`](#counts_covered)
  - [4.3. Property `uncovered`](#counts_uncovered)
  - [4.4. Property `signed`](#counts_signed)
  - [4.5. Property `unsigned`](#counts_unsigned)
  - [4.6. Property `with_sbom`](#counts_with_sbom)
  - [4.7. Property `without_sbom`](#counts_without_sbom)
  - [4.8. Property `errored`](#counts_errored)
- [5. Property `outcomes`](#outcomes)
  - [5.1. CoverageOutcome](#outcomes_items)
    - [5.1.1. Property `image_ref`](#outcomes_items_image_ref)
    - [5.1.2. Property `digest`](#outcomes_items_digest)
      - [5.1.2.1. Property `item 0`](#outcomes_items_digest_anyOf_i0)
      - [5.1.2.2. Property `item 1`](#outcomes_items_digest_anyOf_i1)
    - [5.1.3. Property `covered`](#outcomes_items_covered)
    - [5.1.4. Property `signed`](#outcomes_items_signed)
      - [5.1.4.1. Property `item 0`](#outcomes_items_signed_anyOf_i0)
      - [5.1.4.2. Property `item 1`](#outcomes_items_signed_anyOf_i1)
    - [5.1.5. Property `sbom`](#outcomes_items_sbom)
      - [5.1.5.1. Property `item 0`](#outcomes_items_sbom_anyOf_i0)
      - [5.1.5.2. Property `item 1`](#outcomes_items_sbom_anyOf_i1)
    - [5.1.6. Property `sbom_formats`](#outcomes_items_sbom_formats)
      - [5.1.6.1. Property `item 0`](#outcomes_items_sbom_formats_anyOf_i0)
        - [5.1.6.1.1. item 0 items](#outcomes_items_sbom_formats_anyOf_i0_items)
      - [5.1.6.2. Property `item 1`](#outcomes_items_sbom_formats_anyOf_i1)
    - [5.1.7. Property `policy`](#outcomes_items_policy)
      - [5.1.7.1. Property `item 0`](#outcomes_items_policy_anyOf_i0)
      - [5.1.7.2. Property `item 1`](#outcomes_items_policy_anyOf_i1)
    - [5.1.8. Property `error`](#outcomes_items_error)
      - [5.1.8.1. Property `ErrorInfo`](#outcomes_items_error_anyOf_i0)
        - [5.1.8.1.1. Property `type`](#outcomes_items_error_anyOf_i0_type)
        - [5.1.8.1.2. Property `message`](#outcomes_items_error_anyOf_i0_message)
        - [5.1.8.1.3. Property `exit_code`](#outcomes_items_error_anyOf_i0_exit_code)
      - [5.1.8.2. Property `item 1`](#outcomes_items_error_anyOf_i1)

**Title:** CoverageReport (knock audit JSON output)

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `object`         |
| **Required**              | No               |
| **Additional properties** | Any type allowed |

**Description:** The `knock audit` JSON report. Compatibility rule: within one `apiVersion`, only optional
fields are added; removing, renaming, retyping or changing the meaning of a field bumps it.

| Property                     | Pattern | Type            | Deprecated | Definition                | Title/Description |
| ---------------------------- | ------- | --------------- | ---------- | ------------------------- | ----------------- |
| - [apiVersion](#apiVersion ) | No      | const           | No         | -                         | Apiversion        |
| - [kind](#kind )             | No      | const           | No         | -                         | Kind              |
| + [registries](#registries ) | No      | array of string | No         | -                         | Registries        |
| + [counts](#counts )         | No      | object          | No         | In #/$defs/CoverageCounts | CoverageCounts    |
| + [outcomes](#outcomes )     | No      | array           | No         | -                         | Outcomes          |

## 1. Property `apiVersion` {#apiVersion}

**Title:** Apiversion

|              |                       |
| ------------ | --------------------- |
| **Type**     | `const`               |
| **Required** | No                    |
| **Default**  | `"knock.io/v1alpha1"` |

Specific value: `"knock.io/v1alpha1"`

## 2. Property `kind` {#kind}

**Title:** Kind

|              |                    |
| ------------ | ------------------ |
| **Type**     | `const`            |
| **Required** | No                 |
| **Default**  | `"CoverageReport"` |

Specific value: `"CoverageReport"`

## 3. Property `registries` {#registries}

**Title:** Registries

|              |                   |
| ------------ | ----------------- |
| **Type**     | `array of string` |
| **Required** | Yes               |

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | N/A                |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be       | Description |
| ------------------------------------- | ----------- |
| [registries items](#registries_items) | -           |

### 3.1. registries items {#registries_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

## 4. Property `counts` {#counts}

**Title:** CoverageCounts

|                           |                        |
| ------------------------- | ---------------------- |
| **Type**                  | `object`               |
| **Required**              | Yes                    |
| **Additional properties** | Any type allowed       |
| **Defined in**            | #/$defs/CoverageCounts |

| Property                                | Pattern | Type    | Deprecated | Definition | Title/Description |
| --------------------------------------- | ------- | ------- | ---------- | ---------- | ----------------- |
| - [scanned](#counts_scanned )           | No      | integer | No         | -          | Scanned           |
| - [covered](#counts_covered )           | No      | integer | No         | -          | Covered           |
| - [uncovered](#counts_uncovered )       | No      | integer | No         | -          | Uncovered         |
| - [signed](#counts_signed )             | No      | integer | No         | -          | Signed            |
| - [unsigned](#counts_unsigned )         | No      | integer | No         | -          | Unsigned          |
| - [with_sbom](#counts_with_sbom )       | No      | integer | No         | -          | With Sbom         |
| - [without_sbom](#counts_without_sbom ) | No      | integer | No         | -          | Without Sbom      |
| - [errored](#counts_errored )           | No      | integer | No         | -          | Errored           |

### 4.1. Property `scanned` {#counts_scanned}

**Title:** Scanned

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `0`       |

### 4.2. Property `covered` {#counts_covered}

**Title:** Covered

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `0`       |

### 4.3. Property `uncovered` {#counts_uncovered}

**Title:** Uncovered

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `0`       |

### 4.4. Property `signed` {#counts_signed}

**Title:** Signed

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `0`       |

### 4.5. Property `unsigned` {#counts_unsigned}

**Title:** Unsigned

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `0`       |

### 4.6. Property `with_sbom` {#counts_with_sbom}

**Title:** With Sbom

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `0`       |

### 4.7. Property `without_sbom` {#counts_without_sbom}

**Title:** Without Sbom

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `0`       |

### 4.8. Property `errored` {#counts_errored}

**Title:** Errored

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |
| **Default**  | `0`       |

## 5. Property `outcomes` {#outcomes}

**Title:** Outcomes

|              |         |
| ------------ | ------- |
| **Type**     | `array` |
| **Required** | Yes     |

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | N/A                |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be    | Description |
| ---------------------------------- | ----------- |
| [CoverageOutcome](#outcomes_items) | -           |

### 5.1. CoverageOutcome {#outcomes_items}

**Title:** CoverageOutcome

|                           |                         |
| ------------------------- | ----------------------- |
| **Type**                  | `object`                |
| **Required**              | No                      |
| **Additional properties** | Any type allowed        |
| **Defined in**            | #/$defs/CoverageOutcome |

| Property                                        | Pattern | Type        | Deprecated | Definition | Title/Description                                           |
| ----------------------------------------------- | ------- | ----------- | ---------- | ---------- | ----------------------------------------------------------- |
| + [image_ref](#outcomes_items_image_ref )       | No      | string      | No         | -          | Image Ref                                                   |
| - [digest](#outcomes_items_digest )             | No      | Combination | No         | -          | Digest                                                      |
| - [covered](#outcomes_items_covered )           | No      | boolean     | No         | -          | Covered                                                     |
| - [signed](#outcomes_items_signed )             | No      | Combination | No         | -          | Signed                                                      |
| - [sbom](#outcomes_items_sbom )                 | No      | Combination | No         | -          | Sbom                                                        |
| - [sbom_formats](#outcomes_items_sbom_formats ) | No      | Combination | No         | -          | Sbom Formats                                                |
| - [policy](#outcomes_items_policy )             | No      | Combination | No         | -          | Policy                                                      |
| - [error](#outcomes_items_error )               | No      | Combination | No         | -          | Set when reading this image failed; the probes did not run. |

#### 5.1.1. Property `image_ref` {#outcomes_items_image_ref}

**Title:** Image Ref

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** The image walked, as `<registry>/<repository>:<tag>`.

#### 5.1.2. Property `digest` {#outcomes_items_digest}

**Title:** Digest

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Manifest digest — the stable join key. Null when reading the image failed.

| Any of(Option)                            |
| ----------------------------------------- |
| [item 0](#outcomes_items_digest_anyOf_i0) |
| [item 1](#outcomes_items_digest_anyOf_i1) |

##### 5.1.2.1. Property `item 0` {#outcomes_items_digest_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### 5.1.2.2. Property `item 1` {#outcomes_items_digest_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 5.1.3. Property `covered` {#outcomes_items_covered}

**Title:** Covered

|              |           |
| ------------ | --------- |
| **Type**     | `boolean` |
| **Required** | No        |
| **Default**  | `false`   |

**Description:** The image carries knock's provenance stamp.

#### 5.1.4. Property `signed` {#outcomes_items_signed}

**Title:** Signed

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** A signed attestation referrer was found. Null unless `--signed` and covered.

| Any of(Option)                            |
| ----------------------------------------- |
| [item 0](#outcomes_items_signed_anyOf_i0) |
| [item 1](#outcomes_items_signed_anyOf_i1) |

##### 5.1.4.1. Property `item 0` {#outcomes_items_signed_anyOf_i0}

|              |           |
| ------------ | --------- |
| **Type**     | `boolean` |
| **Required** | No        |

##### 5.1.4.2. Property `item 1` {#outcomes_items_signed_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 5.1.5. Property `sbom` {#outcomes_items_sbom}

**Title:** Sbom

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** An SBOM referrer was found. Null unless `--sbom` and covered.

| Any of(Option)                          |
| --------------------------------------- |
| [item 0](#outcomes_items_sbom_anyOf_i0) |
| [item 1](#outcomes_items_sbom_anyOf_i1) |

##### 5.1.5.1. Property `item 0` {#outcomes_items_sbom_anyOf_i0}

|              |           |
| ------------ | --------- |
| **Type**     | `boolean` |
| **Required** | No        |

##### 5.1.5.2. Property `item 1` {#outcomes_items_sbom_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 5.1.6. Property `sbom_formats` {#outcomes_items_sbom_formats}

**Title:** Sbom Formats

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Sorted SBOM formats (`cyclonedx-json`, `spdx-json`) whose referrer was found; empty when none. Null unless `--sbom` and covered. `sbom` is true exactly when non-empty.

| Any of(Option)                                  |
| ----------------------------------------------- |
| [item 0](#outcomes_items_sbom_formats_anyOf_i0) |
| [item 1](#outcomes_items_sbom_formats_anyOf_i1) |

##### 5.1.6.1. Property `item 0` {#outcomes_items_sbom_formats_anyOf_i0}

|              |                   |
| ------------ | ----------------- |
| **Type**     | `array of string` |
| **Required** | No                |

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | N/A                |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be                             | Description |
| ----------------------------------------------------------- | ----------- |
| [item 0 items](#outcomes_items_sbom_formats_anyOf_i0_items) | -           |

###### 5.1.6.1.1. item 0 items {#outcomes_items_sbom_formats_anyOf_i0_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### 5.1.6.2. Property `item 1` {#outcomes_items_sbom_formats_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 5.1.7. Property `policy` {#outcomes_items_policy}

**Title:** Policy

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** The stamped `{prefix}.policy`, when covered and the label prefix is set.

| Any of(Option)                            |
| ----------------------------------------- |
| [item 0](#outcomes_items_policy_anyOf_i0) |
| [item 1](#outcomes_items_policy_anyOf_i1) |

##### 5.1.7.1. Property `item 0` {#outcomes_items_policy_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### 5.1.7.2. Property `item 1` {#outcomes_items_policy_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 5.1.8. Property `error` {#outcomes_items_error}

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Set when reading this image failed; the probes did not run.

| Any of(Option)                              |
| ------------------------------------------- |
| [ErrorInfo](#outcomes_items_error_anyOf_i0) |
| [item 1](#outcomes_items_error_anyOf_i1)    |

##### 5.1.8.1. Property `ErrorInfo` {#outcomes_items_error_anyOf_i0}

**Title:** ErrorInfo

|                           |                   |
| ------------------------- | ----------------- |
| **Type**                  | `object`          |
| **Required**              | No                |
| **Additional properties** | Any type allowed  |
| **Defined in**            | #/$defs/ErrorInfo |

| Property                                                 | Pattern | Type    | Deprecated | Definition | Title/Description |
| -------------------------------------------------------- | ------- | ------- | ---------- | ---------- | ----------------- |
| + [type](#outcomes_items_error_anyOf_i0_type )           | No      | string  | No         | -          | Type              |
| + [message](#outcomes_items_error_anyOf_i0_message )     | No      | string  | No         | -          | Message           |
| + [exit_code](#outcomes_items_error_anyOf_i0_exit_code ) | No      | integer | No         | -          | Exit Code         |

###### 5.1.8.1.1. Property `type` {#outcomes_items_error_anyOf_i0_type}

**Title:** Type

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

###### 5.1.8.1.2. Property `message` {#outcomes_items_error_anyOf_i0_message}

**Title:** Message

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

###### 5.1.8.1.3. Property `exit_code` {#outcomes_items_error_anyOf_i0_exit_code}

**Title:** Exit Code

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | Yes       |

##### 5.1.8.2. Property `item 1` {#outcomes_items_error_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

----------------------------------------------------------------------------------------------------------------------------
