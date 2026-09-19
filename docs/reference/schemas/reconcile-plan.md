---
sidebar_position: 3
---

# ReconcilePlan (the gate's plan file)

- [1. Property `apiVersion`](#apiVersion)
- [2. Property `kind`](#kind)
- [3. Property `operations`](#operations)
  - [3.1. PlannedOperation](#operations_items)
    - [3.1.1. Property `policy`](#operations_items_policy)
    - [3.1.2. Property `kind`](#operations_items_kind)
    - [3.1.3. Property `destination`](#operations_items_destination)
    - [3.1.4. Property `tag`](#operations_items_tag)
    - [3.1.5. Property `source`](#operations_items_source)
    - [3.1.6. Property `sourceTag`](#operations_items_sourceTag)
    - [3.1.7. Property `sourceDigest`](#operations_items_sourceDigest)

**Title:** ReconcilePlan (the gate's plan file)

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | No          |
| **Additional properties** | Not allowed |

| Property                     | Pattern | Type  | Deprecated | Definition | Title/Description |
| ---------------------------- | ------- | ----- | ---------- | ---------- | ----------------- |
| - [apiVersion](#apiVersion ) | No      | const | No         | -          | Apiversion        |
| - [kind](#kind )             | No      | const | No         | -          | Kind              |
| - [operations](#operations ) | No      | array | No         | -          | Operations        |

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

|              |                   |
| ------------ | ----------------- |
| **Type**     | `const`           |
| **Required** | No                |
| **Default**  | `"ReconcilePlan"` |

Specific value: `"ReconcilePlan"`

## 3. Property `operations` {#operations}

**Title:** Operations

|              |         |
| ------------ | ------- |
| **Type**     | `array` |
| **Required** | No      |

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | N/A                |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be       | Description |
| ------------------------------------- | ----------- |
| [PlannedOperation](#operations_items) | -           |

### 3.1. PlannedOperation {#operations_items}

**Title:** PlannedOperation

|                           |                          |
| ------------------------- | ------------------------ |
| **Type**                  | `object`                 |
| **Required**              | No                       |
| **Additional properties** | Not allowed              |
| **Defined in**            | #/$defs/PlannedOperation |

| Property                                          | Pattern | Type             | Deprecated | Definition | Title/Description |
| ------------------------------------------------- | ------- | ---------------- | ---------- | ---------- | ----------------- |
| + [policy](#operations_items_policy )             | No      | string           | No         | -          | Policy            |
| + [kind](#operations_items_kind )                 | No      | enum (of string) | No         | -          | Kind              |
| + [destination](#operations_items_destination )   | No      | string           | No         | -          | Destination       |
| + [tag](#operations_items_tag )                   | No      | string           | No         | -          | Tag               |
| + [source](#operations_items_source )             | No      | string           | No         | -          | Source            |
| + [sourceTag](#operations_items_sourceTag )       | No      | string           | No         | -          | Sourcetag         |
| + [sourceDigest](#operations_items_sourceDigest ) | No      | string           | No         | -          | Sourcedigest      |

#### 3.1.1. Property `policy` {#operations_items_policy}

**Title:** Policy

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### 3.1.2. Property `kind` {#operations_items_kind}

**Title:** Kind

|              |                    |
| ------------ | ------------------ |
| **Type**     | `enum (of string)` |
| **Required** | Yes                |

Must be one of:
* "import"
* "update"
* "rebuild"

#### 3.1.3. Property `destination` {#operations_items_destination}

**Title:** Destination

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### 3.1.4. Property `tag` {#operations_items_tag}

**Title:** Tag

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### 3.1.5. Property `source` {#operations_items_source}

**Title:** Source

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### 3.1.6. Property `sourceTag` {#operations_items_sourceTag}

**Title:** Sourcetag

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### 3.1.7. Property `sourceDigest` {#operations_items_sourceDigest}

**Title:** Sourcedigest

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

----------------------------------------------------------------------------------------------------------------------------
