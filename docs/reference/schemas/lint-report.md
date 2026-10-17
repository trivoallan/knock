# LintReport (knock lint output)

- [1. Property `apiVersion`](#apiVersion)
- [2. Property `kind`](#kind)
- [3. Property `errors`](#errors)
  - [3.1. Finding](#errors_items)
    - [3.1.1. Property `level`](#errors_items_level)
    - [3.1.2. Property `path`](#errors_items_path)
    - [3.1.3. Property `loc`](#errors_items_loc)
      - [3.1.3.1. Property `item 0`](#errors_items_loc_anyOf_i0)
        - [3.1.3.1.1. item 0 items](#errors_items_loc_anyOf_i0_items)
          - [3.1.3.1.1.1. Property `item 0`](#errors_items_loc_anyOf_i0_items_anyOf_i0)
          - [3.1.3.1.1.2. Property `item 1`](#errors_items_loc_anyOf_i0_items_anyOf_i1)
      - [3.1.3.2. Property `item 1`](#errors_items_loc_anyOf_i1)
    - [3.1.4. Property `message`](#errors_items_message)
    - [3.1.5. Property `related`](#errors_items_related)
      - [3.1.5.1. related items](#errors_items_related_items)
- [4. Property `warnings`](#warnings)
  - [4.1. Finding](#warnings_items)
- [5. Property `skipped`](#skipped)
  - [5.1. Skipped](#skipped_items)
    - [5.1.1. Property `level`](#skipped_items_level)
    - [5.1.2. Property `reason`](#skipped_items_reason)

**Title:** LintReport (knock lint output)

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `object`         |
| **Required**              | No               |
| **Additional properties** | Any type allowed |

**Description:** The `knock lint` report. Compatibility rule: within one `apiVersion`, only optional
fields are added; removing, renaming, retyping or changing the meaning of a field bumps it.

| Property                     | Pattern | Type  | Deprecated | Definition | Title/Description |
| ---------------------------- | ------- | ----- | ---------- | ---------- | ----------------- |
| - [apiVersion](#apiVersion ) | No      | const | No         | -          | Apiversion        |
| - [kind](#kind )             | No      | const | No         | -          | Kind              |
| + [errors](#errors )         | No      | array | No         | -          | Errors            |
| + [warnings](#warnings )     | No      | array | No         | -          | Warnings          |
| + [skipped](#skipped )       | No      | array | No         | -          | Skipped           |

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

|              |                |
| ------------ | -------------- |
| **Type**     | `const`        |
| **Required** | No             |
| **Default**  | `"LintReport"` |

Specific value: `"LintReport"`

## <a name="errors"></a>3. Property `errors`

**Title:** Errors

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

| Each item of this array must be | Description                                                          |
| ------------------------------- | -------------------------------------------------------------------- |
| [Finding](#errors_items)        | One problem in the tree: its level, the file, where in it, and what. |

### <a name="errors_items"></a>3.1. Finding

**Title:** Finding

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `object`         |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Defined in**            | #/$defs/Finding  |

**Description:** One problem in the tree: its level, the file, where in it, and what.

| Property                            | Pattern | Type             | Deprecated | Definition | Title/Description |
| ----------------------------------- | ------- | ---------------- | ---------- | ---------- | ----------------- |
| + [level](#errors_items_level )     | No      | enum (of string) | No         | -          | Level             |
| + [path](#errors_items_path )       | No      | string           | No         | -          | Path              |
| - [loc](#errors_items_loc )         | No      | Combination      | No         | -          | Loc               |
| + [message](#errors_items_message ) | No      | string           | No         | -          | Message           |
| - [related](#errors_items_related ) | No      | array of string  | No         | -          | Related           |

#### <a name="errors_items_level"></a>3.1.1. Property `level`

**Title:** Level

|              |                    |
| ------------ | ------------------ |
| **Type**     | `enum (of string)` |
| **Required** | Yes                |

Must be one of:
* "N1"
* "N2"
* "N3"

#### <a name="errors_items_path"></a>3.1.2. Property `path`

**Title:** Path

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** Policy file, relative to the linted directory (POSIX).

#### <a name="errors_items_loc"></a>3.1.3. Property `loc`

**Title:** Loc

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Location inside the policy document, when known.

| Any of(Option)                       |
| ------------------------------------ |
| [item 0](#errors_items_loc_anyOf_i0) |
| [item 1](#errors_items_loc_anyOf_i1) |

##### <a name="errors_items_loc_anyOf_i0"></a>3.1.3.1. Property `item 0`

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

| Each item of this array must be                  | Description |
| ------------------------------------------------ | ----------- |
| [item 0 items](#errors_items_loc_anyOf_i0_items) | -           |

###### <a name="errors_items_loc_anyOf_i0_items"></a>3.1.3.1.1. item 0 items

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |

| Any of(Option)                                      |
| --------------------------------------------------- |
| [item 0](#errors_items_loc_anyOf_i0_items_anyOf_i0) |
| [item 1](#errors_items_loc_anyOf_i0_items_anyOf_i1) |

###### <a name="errors_items_loc_anyOf_i0_items_anyOf_i0"></a>3.1.3.1.1.1. Property `item 0`

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### <a name="errors_items_loc_anyOf_i0_items_anyOf_i1"></a>3.1.3.1.1.2. Property `item 1`

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |

##### <a name="errors_items_loc_anyOf_i1"></a>3.1.3.2. Property `item 1`

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### <a name="errors_items_message"></a>3.1.4. Property `message`

**Title:** Message

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

#### <a name="errors_items_related"></a>3.1.5. Property `related`

**Title:** Related

|              |                   |
| ------------ | ----------------- |
| **Type**     | `array of string` |
| **Required** | No                |

**Description:** Other files involved (ownership collisions).

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | N/A                |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be              | Description |
| -------------------------------------------- | ----------- |
| [related items](#errors_items_related_items) | -           |

##### <a name="errors_items_related_items"></a>3.1.5.1. related items

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

## <a name="warnings"></a>4. Property `warnings`

**Title:** Warnings

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

| Each item of this array must be | Description                                                          |
| ------------------------------- | -------------------------------------------------------------------- |
| [Finding](#warnings_items)      | One problem in the tree: its level, the file, where in it, and what. |

### <a name="warnings_items"></a>4.1. Finding

**Title:** Finding

|                           |                          |
| ------------------------- | ------------------------ |
| **Type**                  | `object`                 |
| **Required**              | No                       |
| **Additional properties** | Any type allowed         |
| **Same definition as**    | [Finding](#errors_items) |

**Description:** One problem in the tree: its level, the file, where in it, and what.

## <a name="skipped"></a>5. Property `skipped`

**Title:** Skipped

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

| Each item of this array must be | Description                        |
| ------------------------------- | ---------------------------------- |
| [Skipped](#skipped_items)       | A level that did not run, and why. |

### <a name="skipped_items"></a>5.1. Skipped

**Title:** Skipped

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `object`         |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Defined in**            | #/$defs/Skipped  |

**Description:** A level that did not run, and why.

| Property                           | Pattern | Type             | Deprecated | Definition | Title/Description |
| ---------------------------------- | ------- | ---------------- | ---------- | ---------- | ----------------- |
| + [level](#skipped_items_level )   | No      | enum (of string) | No         | -          | Level             |
| + [reason](#skipped_items_reason ) | No      | string           | No         | -          | Reason            |

#### <a name="skipped_items_level"></a>5.1.1. Property `level`

**Title:** Level

|              |                    |
| ------------ | ------------------ |
| **Type**     | `enum (of string)` |
| **Required** | Yes                |

Must be one of:
* "N1"
* "N2"
* "N3"

#### <a name="skipped_items_reason"></a>5.1.2. Property `reason`

**Title:** Reason

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

----------------------------------------------------------------------------------------------------------------------------
