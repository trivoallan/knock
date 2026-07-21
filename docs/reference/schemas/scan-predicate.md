---
sidebar_position: 2
---

# Scan attestation predicate (/scan/v1)

- [1. Property `scanner`](#scanner)
  - [1.1. Property `name`](#scanner_name)
  - [1.2. Property `version`](#scanner_version)
- [2. Property `format`](#format)
- [3. Property `summary`](#summary)
  - [3.1. Property `additionalProperties`](#summary_additionalProperties)
- [4. Property `report_digest`](#report_digest)
- [5. Property `attested_at`](#attested_at)
- [6. Property `builder_id`](#builder_id)

**Title:** Scan attestation predicate (/scan/v1)

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | No          |
| **Additional properties** | Not allowed |

**Description:** knock's normalized scan summary — the signed, verifiable form of `io.knock.scan.*`.

| Property                           | Pattern | Type   | Deprecated | Definition         | Title/Description |
| ---------------------------------- | ------- | ------ | ---------- | ------------------ | ----------------- |
| + [scanner](#scanner )             | No      | object | No         | In #/$defs/Scanner | Scanner           |
| + [format](#format )               | No      | string | No         | -                  | Format            |
| + [summary](#summary )             | No      | object | No         | -                  | Summary           |
| + [report_digest](#report_digest ) | No      | string | No         | -                  | Report Digest     |
| + [attested_at](#attested_at )     | No      | string | No         | -                  | Attested At       |
| + [builder_id](#builder_id )       | No      | string | No         | -                  | Builder Id        |

## 1. Property `scanner` {#scanner}

**Title:** Scanner

|                           |                 |
| ------------------------- | --------------- |
| **Type**                  | `object`        |
| **Required**              | Yes             |
| **Additional properties** | Not allowed     |
| **Defined in**            | #/$defs/Scanner |

**Description:** The upstream scanner that produced the report (knock did not run it).

| Property                       | Pattern | Type   | Deprecated | Definition | Title/Description |
| ------------------------------ | ------- | ------ | ---------- | ---------- | ----------------- |
| + [name](#scanner_name )       | No      | string | No         | -          | Name              |
| + [version](#scanner_version ) | No      | string | No         | -          | Version           |

### 1.1. Property `name` {#scanner_name}

**Title:** Name

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

### 1.2. Property `version` {#scanner_version}

**Title:** Version

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

## 2. Property `format` {#format}

**Title:** Format

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

## 3. Property `summary` {#summary}

**Title:** Summary

|                           |                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------ |
| **Type**                  | `object`                                                                             |
| **Required**              | Yes                                                                                  |
| **Additional properties** | [Each additional property must conform to the schema](#summary_additionalProperties) |

| Property                             | Pattern | Type   | Deprecated | Definition | Title/Description |
| ------------------------------------ | ------- | ------ | ---------- | ---------- | ----------------- |
| - [](#summary_additionalProperties ) | No      | string | No         | -          | -                 |

### 3.1. Property `additionalProperties` {#summary_additionalProperties}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

## 4. Property `report_digest` {#report_digest}

**Title:** Report Digest

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

## 5. Property `attested_at` {#attested_at}

**Title:** Attested At

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** ISO-8601 timestamp of when knock attached and signed this scan. The freshness clock: an admission controller enforces a max-age policy against it (admit only if now - attested_at <= max-age). This signed field is the only trustworthy freshness source — not the unsigned scan-timestamp annotation (the KNOCK_LABEL_PREFIX-prefixed key, e.g. io.knock.scan.timestamp), which exists only for gc.

## 6. Property `builder_id` {#builder_id}

**Title:** Builder Id

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

----------------------------------------------------------------------------------------------------------------------------
