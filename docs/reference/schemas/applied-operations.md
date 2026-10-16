# AppliedOperations (what --apply-plan did with each operation)

- [1. Property `apiVersion`](#apiVersion)
- [2. Property `kind`](#kind)
- [3. Property `operations`](#operations)
  - [3.1. AppliedOperation](#operations_items)
    - [3.1.1. Property `policy`](#operations_items_policy)
    - [3.1.2. Property `destination`](#operations_items_destination)
    - [3.1.3. Property `tag`](#operations_items_tag)
    - [3.1.4. Property `kind`](#operations_items_kind)
    - [3.1.5. Property `sourceDigest`](#operations_items_sourceDigest)
    - [3.1.6. Property `writtenDigest`](#operations_items_writtenDigest)
      - [3.1.6.1. Property `item 0`](#operations_items_writtenDigest_anyOf_i0)
      - [3.1.6.2. Property `item 1`](#operations_items_writtenDigest_anyOf_i1)
    - [3.1.7. Property `reason`](#operations_items_reason)
      - [3.1.7.1. Property `item 0`](#operations_items_reason_anyOf_i0)
      - [3.1.7.2. Property `item 1`](#operations_items_reason_anyOf_i1)

**Title:** AppliedOperations (what --apply-plan did with each operation)

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | No          |
| **Additional properties** | Not allowed |

**Description:** What `--apply-plan` did with each operation: the source → written digest link an
orchestrator journals, and the reasons it withheld what it could not honour.

| Property                     | Pattern | Type  | Deprecated | Definition | Title/Description |
| ---------------------------- | ------- | ----- | ---------- | ---------- | ----------------- |
| - [apiVersion](#apiVersion ) | No      | const | No         | -          | Apiversion        |
| - [kind](#kind )             | No      | const | No         | -          | Kind              |
| - [operations](#operations ) | No      | array | No         | -          | Operations        |

## <a name="apiVersion"></a>1. Property `apiVersion`

**Title:** Apiversion

|              |                       |
| ------------ | --------------------- |
| **Type**     | `const`               |
| **Required** | No                    |
| **Default**  | `"knock.io/v1alpha1"` |

Specific value: `"knock.io/v1alpha1"`

## <a name="kind"></a>2. Property `kind`

**Title:** Kind

|              |                       |
| ------------ | --------------------- |
| **Type**     | `const`               |
| **Required** | No                    |
| **Default**  | `"AppliedOperations"` |

Specific value: `"AppliedOperations"`

## <a name="operations"></a>3. Property `operations`

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

| Each item of this array must be       | Description                                                         |
| ------------------------------------- | ------------------------------------------------------------------- |
| [AppliedOperation](#operations_items) | One operation '--apply-plan' applied, held in staging, or withheld. |

### <a name="operations_items"></a>3.1. AppliedOperation

**Title:** AppliedOperation

|                           |                          |
| ------------------------- | ------------------------ |
| **Type**                  | `object`                 |
| **Required**              | No                       |
| **Additional properties** | Not allowed              |
| **Defined in**            | #/$defs/AppliedOperation |

**Description:** One operation `--apply-plan` applied, held in staging, or withheld.

| Property                                            | Pattern | Type        | Deprecated | Definition | Title/Description |
| --------------------------------------------------- | ------- | ----------- | ---------- | ---------- | ----------------- |
| + [policy](#operations_items_policy )               | No      | string      | No         | -          | Policy            |
| + [destination](#operations_items_destination )     | No      | string      | No         | -          | Destination       |
| + [tag](#operations_items_tag )                     | No      | string      | No         | -          | Tag               |
| + [kind](#operations_items_kind )                   | No      | string      | No         | -          | Kind              |
| + [sourceDigest](#operations_items_sourceDigest )   | No      | string      | No         | -          | Sourcedigest      |
| - [writtenDigest](#operations_items_writtenDigest ) | No      | Combination | No         | -          | Writtendigest     |
| - [reason](#operations_items_reason )               | No      | Combination | No         | -          | Reason            |

#### <a name="operations_items_policy"></a>3.1.1. Property `policy`

**Title:** Policy

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_destination"></a>3.1.2. Property `destination`

**Title:** Destination

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_tag"></a>3.1.3. Property `tag`

**Title:** Tag

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_kind"></a>3.1.4. Property `kind`

**Title:** Kind

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_sourceDigest"></a>3.1.5. Property `sourceDigest`

**Title:** Sourcedigest

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_writtenDigest"></a>3.1.6. Property `writtenDigest`

**Title:** Writtendigest

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

| Any of(Option)                                     |
| -------------------------------------------------- |
| [item 0](#operations_items_writtenDigest_anyOf_i0) |
| [item 1](#operations_items_writtenDigest_anyOf_i1) |

##### <a name="operations_items_writtenDigest_anyOf_i0"></a>3.1.6.1. Property `item 0`

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### <a name="operations_items_writtenDigest_anyOf_i1"></a>3.1.6.2. Property `item 1`

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### <a name="operations_items_reason"></a>3.1.7. Property `reason`

**Title:** Reason

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

| Any of(Option)                              |
| ------------------------------------------- |
| [item 0](#operations_items_reason_anyOf_i0) |
| [item 1](#operations_items_reason_anyOf_i1) |

##### <a name="operations_items_reason_anyOf_i0"></a>3.1.7.1. Property `item 0`

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### <a name="operations_items_reason_anyOf_i1"></a>3.1.7.2. Property `item 1`

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

----------------------------------------------------------------------------------------------------------------------------
