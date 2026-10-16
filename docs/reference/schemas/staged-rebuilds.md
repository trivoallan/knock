# StagedRebuilds (the remediated images held in staging)

- [1. Property `apiVersion`](#apiVersion)
- [2. Property `kind`](#kind)
- [3. Property `entries`](#entries)
  - [3.1. StagedEntry](#entries_items)
    - [3.1.1. Property `policy`](#entries_items_policy)
    - [3.1.2. Property `import`](#entries_items_import)
    - [3.1.3. Property `variant`](#entries_items_variant)
    - [3.1.4. Property `kind`](#entries_items_kind)
    - [3.1.5. Property `destination`](#entries_items_destination)
    - [3.1.6. Property `tag`](#entries_items_tag)
    - [3.1.7. Property `source`](#entries_items_source)
    - [3.1.8. Property `sourceTag`](#entries_items_sourceTag)
    - [3.1.9. Property `sourceDigest`](#entries_items_sourceDigest)
    - [3.1.10. Property `staged`](#entries_items_staged)
    - [3.1.11. Property `stagedDigest`](#entries_items_stagedDigest)
    - [3.1.12. Property `aliases`](#entries_items_aliases)
      - [3.1.12.1. aliases items](#entries_items_aliases_items)
    - [3.1.13. Property `epoch`](#entries_items_epoch)
      - [3.1.13.1. Property `item 0`](#entries_items_epoch_anyOf_i0)
      - [3.1.13.2. Property `item 1`](#entries_items_epoch_anyOf_i1)

**Title:** StagedRebuilds (the remediated images held in staging)

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | No          |
| **Additional properties** | Not allowed |

| Property                     | Pattern | Type  | Deprecated | Definition | Title/Description |
| ---------------------------- | ------- | ----- | ---------- | ---------- | ----------------- |
| - [apiVersion](#apiVersion ) | No      | const | No         | -          | Apiversion        |
| - [kind](#kind )             | No      | const | No         | -          | Kind              |
| - [entries](#entries )       | No      | array | No         | -          | Entries           |

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

|              |                    |
| ------------ | ------------------ |
| **Type**     | `const`            |
| **Required** | No                 |
| **Default**  | `"StagedRebuilds"` |

Specific value: `"StagedRebuilds"`

## <a name="entries"></a>3. Property `entries`

**Title:** Entries

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

| Each item of this array must be | Description                                                                  |
| ------------------------------- | ---------------------------------------------------------------------------- |
| [StagedEntry](#entries_items)   | One rebuilt image held in the staging registry, and where it is meant to go. |

### <a name="entries_items"></a>3.1. StagedEntry

**Title:** StagedEntry

|                           |                     |
| ------------------------- | ------------------- |
| **Type**                  | `object`            |
| **Required**              | No                  |
| **Additional properties** | Not allowed         |
| **Defined in**            | #/$defs/StagedEntry |

**Description:** One rebuilt image held in the staging registry, and where it is meant to go.

| Property                                       | Pattern | Type             | Deprecated | Definition | Title/Description |
| ---------------------------------------------- | ------- | ---------------- | ---------- | ---------- | ----------------- |
| + [policy](#entries_items_policy )             | No      | string           | No         | -          | Policy            |
| + [import](#entries_items_import )             | No      | string           | No         | -          | Import            |
| + [variant](#entries_items_variant )           | No      | string           | No         | -          | Variant           |
| + [kind](#entries_items_kind )                 | No      | enum (of string) | No         | -          | Kind              |
| + [destination](#entries_items_destination )   | No      | string           | No         | -          | Destination       |
| + [tag](#entries_items_tag )                   | No      | string           | No         | -          | Tag               |
| + [source](#entries_items_source )             | No      | string           | No         | -          | Source            |
| + [sourceTag](#entries_items_sourceTag )       | No      | string           | No         | -          | Sourcetag         |
| + [sourceDigest](#entries_items_sourceDigest ) | No      | string           | No         | -          | Sourcedigest      |
| + [staged](#entries_items_staged )             | No      | string           | No         | -          | Staged            |
| + [stagedDigest](#entries_items_stagedDigest ) | No      | string           | No         | -          | Stageddigest      |
| - [aliases](#entries_items_aliases )           | No      | array of string  | No         | -          | Aliases           |
| - [epoch](#entries_items_epoch )               | No      | Combination      | No         | -          | Epoch             |

#### <a name="entries_items_policy"></a>3.1.1. Property `policy`

**Title:** Policy

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_import"></a>3.1.2. Property `import`

**Title:** Import

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_variant"></a>3.1.3. Property `variant`

**Title:** Variant

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_kind"></a>3.1.4. Property `kind`

**Title:** Kind

|              |                    |
| ------------ | ------------------ |
| **Type**     | `enum (of string)` |
| **Required** | Yes                |

Must be one of:
* "import"
* "update"
* "rebuild"

#### <a name="entries_items_destination"></a>3.1.5. Property `destination`

**Title:** Destination

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_tag"></a>3.1.6. Property `tag`

**Title:** Tag

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_source"></a>3.1.7. Property `source`

**Title:** Source

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_sourceTag"></a>3.1.8. Property `sourceTag`

**Title:** Sourcetag

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_sourceDigest"></a>3.1.9. Property `sourceDigest`

**Title:** Sourcedigest

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_staged"></a>3.1.10. Property `staged`

**Title:** Staged

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_stagedDigest"></a>3.1.11. Property `stagedDigest`

**Title:** Stageddigest

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="entries_items_aliases"></a>3.1.12. Property `aliases`

**Title:** Aliases

|              |                   |
| ------------ | ----------------- |
| **Type**     | `array of string` |
| **Required** | No                |
| **Default**  | `[]`              |

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | N/A                |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be               | Description |
| --------------------------------------------- | ----------- |
| [aliases items](#entries_items_aliases_items) | -           |

##### <a name="entries_items_aliases_items"></a>3.1.12.1. aliases items

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

#### <a name="entries_items_epoch"></a>3.1.13. Property `epoch`

**Title:** Epoch

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

| Any of(Option)                          |
| --------------------------------------- |
| [item 0](#entries_items_epoch_anyOf_i0) |
| [item 1](#entries_items_epoch_anyOf_i1) |

##### <a name="entries_items_epoch_anyOf_i0"></a>3.1.13.1. Property `item 0`

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

##### <a name="entries_items_epoch_anyOf_i1"></a>3.1.13.2. Property `item 1`

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

----------------------------------------------------------------------------------------------------------------------------
