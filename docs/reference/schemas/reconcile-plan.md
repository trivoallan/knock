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
    - [3.1.8. Property `transformed`](#operations_items_transformed)
    - [3.1.9. Property `remediate`](#operations_items_remediate)
      - [3.1.9.1. Property `RemediationOrder`](#operations_items_remediate_anyOf_i0)
        - [3.1.9.1.1. Property `epoch`](#operations_items_remediate_anyOf_i0_epoch)
      - [3.1.9.2. Property `item 1`](#operations_items_remediate_anyOf_i1)
    - [3.1.10. Property `remediated`](#operations_items_remediated)

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

|              |                   |
| ------------ | ----------------- |
| **Type**     | `const`           |
| **Required** | No                |
| **Default**  | `"ReconcilePlan"` |

Specific value: `"ReconcilePlan"`

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

| Each item of this array must be       | Description |
| ------------------------------------- | ----------- |
| [PlannedOperation](#operations_items) | -           |

### <a name="operations_items"></a>3.1. PlannedOperation

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
| - [transformed](#operations_items_transformed )   | No      | boolean          | No         | -          | Transformed       |
| - [remediate](#operations_items_remediate )       | No      | Combination      | No         | -          | -                 |
| - [remediated](#operations_items_remediated )     | No      | boolean          | No         | -          | Remediated        |

#### <a name="operations_items_policy"></a>3.1.1. Property `policy`

**Title:** Policy

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_kind"></a>3.1.2. Property `kind`

**Title:** Kind

|              |                    |
| ------------ | ------------------ |
| **Type**     | `enum (of string)` |
| **Required** | Yes                |

Must be one of:
* "import"
* "update"
* "rebuild"

#### <a name="operations_items_destination"></a>3.1.3. Property `destination`

**Title:** Destination

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_tag"></a>3.1.4. Property `tag`

**Title:** Tag

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_source"></a>3.1.5. Property `source`

**Title:** Source

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_sourceTag"></a>3.1.6. Property `sourceTag`

**Title:** Sourcetag

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_sourceDigest"></a>3.1.7. Property `sourceDigest`

**Title:** Sourcedigest

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="operations_items_transformed"></a>3.1.8. Property `transformed`

**Title:** Transformed

|              |           |
| ------------ | --------- |
| **Type**     | `boolean` |
| **Required** | No        |
| **Default**  | `false`   |

#### <a name="operations_items_remediate"></a>3.1.9. Property `remediate`

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

| Any of(Option)                                           |
| -------------------------------------------------------- |
| [RemediationOrder](#operations_items_remediate_anyOf_i0) |
| [item 1](#operations_items_remediate_anyOf_i1)           |

##### <a name="operations_items_remediate_anyOf_i0"></a>3.1.9.1. Property `RemediationOrder`

**Title:** RemediationOrder

|                           |                          |
| ------------------------- | ------------------------ |
| **Type**                  | `object`                 |
| **Required**              | No                       |
| **Additional properties** | Not allowed              |
| **Defined in**            | #/$defs/RemediationOrder |

| Property                                               | Pattern | Type   | Deprecated | Definition | Title/Description |
| ------------------------------------------------------ | ------- | ------ | ---------- | ---------- | ----------------- |
| + [epoch](#operations_items_remediate_anyOf_i0_epoch ) | No      | string | No         | -          | Epoch             |

###### <a name="operations_items_remediate_anyOf_i0_epoch"></a>3.1.9.1.1. Property `epoch`

**Title:** Epoch

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

| Restrictions                      |                                                                                                       |
| --------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Must match regular expression** | ```^[A-Za-z0-9._-]{1,64}$``` [Test](https://regex101.com/?regex=%5E%5BA-Za-z0-9._-%5D%7B1%2C64%7D%24) |

##### <a name="operations_items_remediate_anyOf_i1"></a>3.1.9.2. Property `item 1`

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### <a name="operations_items_remediated"></a>3.1.10. Property `remediated`

**Title:** Remediated

|              |           |
| ------------ | --------- |
| **Type**     | `boolean` |
| **Required** | No        |
| **Default**  | `false`   |

----------------------------------------------------------------------------------------------------------------------------
