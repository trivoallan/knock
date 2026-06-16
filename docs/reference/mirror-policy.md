---
sidebar_position: 1
---

# MirrorPolicy

- [1. Property `MirrorPolicy > apiVersion`](#apiVersion)
- [2. Property `MirrorPolicy > kind`](#kind)
- [3. Property `MirrorPolicy > metadata`](#metadata)
  - [3.1. Property `MirrorPolicy > metadata > name`](#metadata_name)
  - [3.2. Property `MirrorPolicy > metadata > labels`](#metadata_labels)
    - [3.2.1. Property `MirrorPolicy > metadata > labels > additionalProperties`](#metadata_labels_additionalProperties)
- [4. Property `MirrorPolicy > spec`](#spec)
  - [4.1. Property `MirrorPolicy > spec > artifactType`](#spec_artifactType)
  - [4.2. Property `MirrorPolicy > spec > source`](#spec_source)
    - [4.2.1. Property `MirrorPolicy > spec > source > registry`](#spec_source_registry)
    - [4.2.2. Property `MirrorPolicy > spec > source > repository`](#spec_source_repository)
  - [4.3. Property `MirrorPolicy > spec > deletionMode`](#spec_deletionMode)
    - [4.3.1. Property `MirrorPolicy > spec > deletionMode > anyOf > DeletionMode`](#spec_deletionMode_anyOf_i0)
    - [4.3.2. Property `MirrorPolicy > spec > deletionMode > anyOf > item 1`](#spec_deletionMode_anyOf_i1)
  - [4.4. Property `MirrorPolicy > spec > defaults`](#spec_defaults)
    - [4.4.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults`](#spec_defaults_anyOf_i0)
      - [4.4.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations`](#spec_defaults_anyOf_i0_destinations)
        - [4.4.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0`](#spec_defaults_anyOf_i0_destinations_anyOf_i0)
          - [4.4.1.1.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items)
            - [4.4.1.1.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > registry`](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_registry)
              - [4.4.1.1.1.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > registry > anyOf > item 0`](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_registry_anyOf_i0)
              - [4.4.1.1.1.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > registry > anyOf > item 1`](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_registry_anyOf_i1)
            - [4.4.1.1.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > project`](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_project)
            - [4.4.1.1.1.1.3. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > repository`](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_repository)
        - [4.4.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 1`](#spec_defaults_anyOf_i0_destinations_anyOf_i1)
      - [4.4.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform`](#spec_defaults_anyOf_i0_transform)
        - [4.4.1.2.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0`](#spec_defaults_anyOf_i0_transform_anyOf_i0)
          - [4.4.1.2.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > TransformStep](#spec_defaults_anyOf_i0_transform_anyOf_i0_items)
            - [4.4.1.2.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 0`](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0)
              - [4.4.1.2.1.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 0 > injectCA`](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0_injectCA)
                - [4.4.1.2.1.1.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 0 > injectCA > certs`](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0_injectCA_certs)
                  - [4.4.1.2.1.1.1.1.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 0 > injectCA > certs > certs items](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0_injectCA_certs_items)
            - [4.4.1.2.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 1`](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i1)
              - [4.4.1.2.1.1.2.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 1 > rewritePackageSources`](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i1_rewritePackageSources)
                - [4.4.1.2.1.1.2.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 1 > rewritePackageSources > mirror`](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i1_rewritePackageSources_mirror)
            - [4.4.1.2.1.1.3. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 2`](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i2)
              - [4.4.1.2.1.1.3.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 2 > setTimezone`](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i2_setTimezone)
                - [4.4.1.2.1.1.3.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 2 > setTimezone > zone`](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i2_setTimezone_zone)
        - [4.4.1.2.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 1`](#spec_defaults_anyOf_i0_transform_anyOf_i1)
      - [4.4.1.3. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive`](#spec_defaults_anyOf_i0_archive)
        - [4.4.1.3.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive`](#spec_defaults_anyOf_i0_archive_anyOf_i0)
          - [4.4.1.3.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > keep`](#spec_defaults_anyOf_i0_archive_anyOf_i0_keep)
            - [4.4.1.3.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > keep > anyOf > item 0`](#spec_defaults_anyOf_i0_archive_anyOf_i0_keep_anyOf_i0)
            - [4.4.1.3.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > keep > anyOf > item 1`](#spec_defaults_anyOf_i0_archive_anyOf_i0_keep_anyOf_i1)
          - [4.4.1.3.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > olderThanDays`](#spec_defaults_anyOf_i0_archive_anyOf_i0_olderThanDays)
            - [4.4.1.3.1.2.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > olderThanDays > anyOf > item 0`](#spec_defaults_anyOf_i0_archive_anyOf_i0_olderThanDays_anyOf_i0)
            - [4.4.1.3.1.2.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > olderThanDays > anyOf > item 1`](#spec_defaults_anyOf_i0_archive_anyOf_i0_olderThanDays_anyOf_i1)
        - [4.4.1.3.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > item 1`](#spec_defaults_anyOf_i0_archive_anyOf_i1)
      - [4.4.1.4. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags`](#spec_defaults_anyOf_i0_tags)
        - [4.4.1.4.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection`](#spec_defaults_anyOf_i0_tags_anyOf_i0)
          - [4.4.1.4.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > includeRegex`](#spec_defaults_anyOf_i0_tags_anyOf_i0_includeRegex)
            - [4.4.1.4.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > includeRegex > anyOf > item 0`](#spec_defaults_anyOf_i0_tags_anyOf_i0_includeRegex_anyOf_i0)
            - [4.4.1.4.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > includeRegex > anyOf > item 1`](#spec_defaults_anyOf_i0_tags_anyOf_i0_includeRegex_anyOf_i1)
          - [4.4.1.4.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > excludeRegex`](#spec_defaults_anyOf_i0_tags_anyOf_i0_excludeRegex)
            - [4.4.1.4.1.2.1. MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > excludeRegex > excludeRegex items](#spec_defaults_anyOf_i0_tags_anyOf_i0_excludeRegex_items)
          - [4.4.1.4.1.3. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > semverOnly`](#spec_defaults_anyOf_i0_tags_anyOf_i0_semverOnly)
          - [4.4.1.4.1.4. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > names`](#spec_defaults_anyOf_i0_tags_anyOf_i0_names)
            - [4.4.1.4.1.4.1. MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > names > names items](#spec_defaults_anyOf_i0_tags_anyOf_i0_names_items)
          - [4.4.1.4.1.5. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > aliases`](#spec_defaults_anyOf_i0_tags_anyOf_i0_aliases)
            - [4.4.1.4.1.5.1. MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > aliases > aliases items](#spec_defaults_anyOf_i0_tags_anyOf_i0_aliases_items)
        - [4.4.1.4.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > item 1`](#spec_defaults_anyOf_i0_tags_anyOf_i1)
      - [4.4.1.5. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > platforms`](#spec_defaults_anyOf_i0_platforms)
        - [4.4.1.5.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > platforms > anyOf > item 0`](#spec_defaults_anyOf_i0_platforms_anyOf_i0)
          - [4.4.1.5.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > platforms > anyOf > item 0 > item 0 items](#spec_defaults_anyOf_i0_platforms_anyOf_i0_items)
        - [4.4.1.5.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > platforms > anyOf > item 1`](#spec_defaults_anyOf_i0_platforms_anyOf_i1)
      - [4.4.1.6. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > owners`](#spec_defaults_anyOf_i0_owners)
        - [4.4.1.6.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > owners > anyOf > item 0`](#spec_defaults_anyOf_i0_owners_anyOf_i0)
          - [4.4.1.6.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > owners > anyOf > item 0 > item 0 items](#spec_defaults_anyOf_i0_owners_anyOf_i0_items)
        - [4.4.1.6.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > owners > anyOf > item 1`](#spec_defaults_anyOf_i0_owners_anyOf_i1)
      - [4.4.1.7. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > vendor`](#spec_defaults_anyOf_i0_vendor)
        - [4.4.1.7.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > vendor > anyOf > item 0`](#spec_defaults_anyOf_i0_vendor_anyOf_i0)
        - [4.4.1.7.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > vendor > anyOf > item 1`](#spec_defaults_anyOf_i0_vendor_anyOf_i1)
    - [4.4.2. Property `MirrorPolicy > spec > defaults > anyOf > item 1`](#spec_defaults_anyOf_i1)
  - [4.5. Property `MirrorPolicy > spec > imports`](#spec_imports)
    - [4.5.1. MirrorPolicy > spec > imports > ImportProfile](#spec_imports_items)
      - [4.5.1.1. Property `MirrorPolicy > spec > imports > ImportProfile > name`](#spec_imports_items_name)
      - [4.5.1.2. Property `MirrorPolicy > spec > imports > ImportProfile > tags`](#spec_imports_items_tags)
      - [4.5.1.3. Property `MirrorPolicy > spec > imports > ImportProfile > destinations`](#spec_imports_items_destinations)
        - [4.5.1.3.1. Property `MirrorPolicy > spec > imports > ImportProfile > destinations > anyOf > item 0`](#spec_imports_items_destinations_anyOf_i0)
          - [4.5.1.3.1.1. MirrorPolicy > spec > imports > ImportProfile > destinations > anyOf > item 0 > Destination](#spec_imports_items_destinations_anyOf_i0_items)
        - [4.5.1.3.2. Property `MirrorPolicy > spec > imports > ImportProfile > destinations > anyOf > item 1`](#spec_imports_items_destinations_anyOf_i1)
      - [4.5.1.4. Property `MirrorPolicy > spec > imports > ImportProfile > transform`](#spec_imports_items_transform)
        - [4.5.1.4.1. Property `MirrorPolicy > spec > imports > ImportProfile > transform > anyOf > item 0`](#spec_imports_items_transform_anyOf_i0)
          - [4.5.1.4.1.1. MirrorPolicy > spec > imports > ImportProfile > transform > anyOf > item 0 > TransformStep](#spec_imports_items_transform_anyOf_i0_items)
        - [4.5.1.4.2. Property `MirrorPolicy > spec > imports > ImportProfile > transform > anyOf > item 1`](#spec_imports_items_transform_anyOf_i1)
      - [4.5.1.5. Property `MirrorPolicy > spec > imports > ImportProfile > archive`](#spec_imports_items_archive)
        - [4.5.1.5.1. Property `MirrorPolicy > spec > imports > ImportProfile > archive > anyOf > Archive`](#spec_imports_items_archive_anyOf_i0)
        - [4.5.1.5.2. Property `MirrorPolicy > spec > imports > ImportProfile > archive > anyOf > item 1`](#spec_imports_items_archive_anyOf_i1)
      - [4.5.1.6. Property `MirrorPolicy > spec > imports > ImportProfile > platforms`](#spec_imports_items_platforms)
        - [4.5.1.6.1. Property `MirrorPolicy > spec > imports > ImportProfile > platforms > anyOf > item 0`](#spec_imports_items_platforms_anyOf_i0)
          - [4.5.1.6.1.1. MirrorPolicy > spec > imports > ImportProfile > platforms > anyOf > item 0 > item 0 items](#spec_imports_items_platforms_anyOf_i0_items)
        - [4.5.1.6.2. Property `MirrorPolicy > spec > imports > ImportProfile > platforms > anyOf > item 1`](#spec_imports_items_platforms_anyOf_i1)
      - [4.5.1.7. Property `MirrorPolicy > spec > imports > ImportProfile > variants`](#spec_imports_items_variants)
        - [4.5.1.7.1. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0`](#spec_imports_items_variants_anyOf_i0)
          - [4.5.1.7.1.1. MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant](#spec_imports_items_variants_anyOf_i0_items)
            - [4.5.1.7.1.1.1. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > name`](#spec_imports_items_variants_anyOf_i0_items_name)
            - [4.5.1.7.1.1.2. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > suffix`](#spec_imports_items_variants_anyOf_i0_items_suffix)
            - [4.5.1.7.1.1.3. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > transform`](#spec_imports_items_variants_anyOf_i0_items_transform)
              - [4.5.1.7.1.1.3.1. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > transform > anyOf > item 0`](#spec_imports_items_variants_anyOf_i0_items_transform_anyOf_i0)
                - [4.5.1.7.1.1.3.1.1. MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > transform > anyOf > item 0 > TransformStep](#spec_imports_items_variants_anyOf_i0_items_transform_anyOf_i0_items)
              - [4.5.1.7.1.1.3.2. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > transform > anyOf > item 1`](#spec_imports_items_variants_anyOf_i0_items_transform_anyOf_i1)
        - [4.5.1.7.2. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 1`](#spec_imports_items_variants_anyOf_i1)
      - [4.5.1.8. Property `MirrorPolicy > spec > imports > ImportProfile > owners`](#spec_imports_items_owners)
        - [4.5.1.8.1. Property `MirrorPolicy > spec > imports > ImportProfile > owners > anyOf > item 0`](#spec_imports_items_owners_anyOf_i0)
          - [4.5.1.8.1.1. MirrorPolicy > spec > imports > ImportProfile > owners > anyOf > item 0 > item 0 items](#spec_imports_items_owners_anyOf_i0_items)
        - [4.5.1.8.2. Property `MirrorPolicy > spec > imports > ImportProfile > owners > anyOf > item 1`](#spec_imports_items_owners_anyOf_i1)
      - [4.5.1.9. Property `MirrorPolicy > spec > imports > ImportProfile > vendor`](#spec_imports_items_vendor)
        - [4.5.1.9.1. Property `MirrorPolicy > spec > imports > ImportProfile > vendor > anyOf > item 0`](#spec_imports_items_vendor_anyOf_i0)
        - [4.5.1.9.2. Property `MirrorPolicy > spec > imports > ImportProfile > vendor > anyOf > item 1`](#spec_imports_items_vendor_anyOf_i1)

**Title:** MirrorPolicy

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | No          |
| **Additional properties** | Not allowed |

| Property                     | Pattern | Type   | Deprecated | Definition          | Title/Description |
| ---------------------------- | ------- | ------ | ---------- | ------------------- | ----------------- |
| + [apiVersion](#apiVersion ) | No      | const  | No         | -                   | Apiversion        |
| + [kind](#kind )             | No      | const  | No         | -                   | Kind              |
| + [metadata](#metadata )     | No      | object | No         | In #/$defs/Metadata | Metadata          |
| + [spec](#spec )             | No      | object | No         | In #/$defs/Spec     | Spec              |

## 1. Property `MirrorPolicy > apiVersion` {#apiVersion}

**Title:** Apiversion

|              |         |
| ------------ | ------- |
| **Type**     | `const` |
| **Required** | Yes     |

**Description:** API version; pinned to `houba.io/v1alpha1`.

Specific value: `"houba.io/v1alpha1"`

## 2. Property `MirrorPolicy > kind` {#kind}

**Title:** Kind

|              |         |
| ------------ | ------- |
| **Type**     | `const` |
| **Required** | Yes     |

**Description:** Resource kind; always `MirrorPolicy`.

Specific value: `"MirrorPolicy"`

## 3. Property `MirrorPolicy > metadata` {#metadata}

**Title:** Metadata

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `object`         |
| **Required**              | Yes              |
| **Additional properties** | Not allowed      |
| **Defined in**            | #/$defs/Metadata |

**Description:** Policy metadata (name, labels).

| Property                      | Pattern | Type   | Deprecated | Definition | Title/Description |
| ----------------------------- | ------- | ------ | ---------- | ---------- | ----------------- |
| + [name](#metadata_name )     | No      | string | No         | -          | Name              |
| - [labels](#metadata_labels ) | No      | object | No         | -          | Labels            |

### 3.1. Property `MirrorPolicy > metadata > name` {#metadata_name}

**Title:** Name

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** Policy name; stamped as `io.houba.policy` and used for collision checks.

### 3.2. Property `MirrorPolicy > metadata > labels` {#metadata_labels}

**Title:** Labels

|                           |                                                                                              |
| ------------------------- | -------------------------------------------------------------------------------------------- |
| **Type**                  | `object`                                                                                     |
| **Required**              | No                                                                                           |
| **Additional properties** | [Each additional property must conform to the schema](#metadata_labels_additionalProperties) |

**Description:** Free-form labels (not stamped).

| Property                                     | Pattern | Type   | Deprecated | Definition | Title/Description |
| -------------------------------------------- | ------- | ------ | ---------- | ---------- | ----------------- |
| - [](#metadata_labels_additionalProperties ) | No      | string | No         | -          | -                 |

#### 3.2.1. Property `MirrorPolicy > metadata > labels > additionalProperties` {#metadata_labels_additionalProperties}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

## 4. Property `MirrorPolicy > spec` {#spec}

**Title:** Spec

|                           |              |
| ------------------------- | ------------ |
| **Type**                  | `object`     |
| **Required**              | Yes          |
| **Additional properties** | Not allowed  |
| **Defined in**            | #/$defs/Spec |

**Description:** Policy specification.

| Property                              | Pattern | Type             | Deprecated | Definition              | Title/Description                                                               |
| ------------------------------------- | ------- | ---------------- | ---------- | ----------------------- | ------------------------------------------------------------------------------- |
| + [artifactType](#spec_artifactType ) | No      | enum (of string) | No         | In #/$defs/ArtifactType | ArtifactType                                                                    |
| + [source](#spec_source )             | No      | object           | No         | In #/$defs/Source       | Source                                                                          |
| - [deletionMode](#spec_deletionMode ) | No      | Combination      | No         | -                       | Policy-level deletion mode; \`null\` ⇒ defer to the destination/global cascade. |
| - [defaults](#spec_defaults )         | No      | Combination      | No         | -                       | Defaults inherited by every import.                                             |
| + [imports](#spec_imports )           | No      | array            | No         | -                       | Imports                                                                         |

### 4.1. Property `MirrorPolicy > spec > artifactType` {#spec_artifactType}

**Title:** ArtifactType

|                |                      |
| -------------- | -------------------- |
| **Type**       | `enum (of string)`   |
| **Required**   | Yes                  |
| **Defined in** | #/$defs/ArtifactType |

**Description:** Artifact kind: `image` | `helmChart` | `generic`.

Must be one of:
* "image"
* "helmChart"
* "generic"

### 4.2. Property `MirrorPolicy > spec > source` {#spec_source}

**Title:** Source

|                           |                |
| ------------------------- | -------------- |
| **Type**                  | `object`       |
| **Required**              | Yes            |
| **Additional properties** | Not allowed    |
| **Defined in**            | #/$defs/Source |

**Description:** Upstream source registry + repository.

| Property                                 | Pattern | Type   | Deprecated | Definition | Title/Description |
| ---------------------------------------- | ------- | ------ | ---------- | ---------- | ----------------- |
| + [registry](#spec_source_registry )     | No      | string | No         | -          | Registry          |
| + [repository](#spec_source_repository ) | No      | string | No         | -          | Repository        |

#### 4.2.1. Property `MirrorPolicy > spec > source > registry` {#spec_source_registry}

**Title:** Registry

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** Source registry host, e.g. `docker.io`.

#### 4.2.2. Property `MirrorPolicy > spec > source > repository` {#spec_source_repository}

**Title:** Repository

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** Source repository, e.g. `library/redis`.

### 4.3. Property `MirrorPolicy > spec > deletionMode` {#spec_deletionMode}

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Policy-level deletion mode; `null` ⇒ defer to the destination/global cascade.

| Any of(Option)                              |
| ------------------------------------------- |
| [DeletionMode](#spec_deletionMode_anyOf_i0) |
| [item 1](#spec_deletionMode_anyOf_i1)       |

#### 4.3.1. Property `MirrorPolicy > spec > deletionMode > anyOf > DeletionMode` {#spec_deletionMode_anyOf_i0}

**Title:** DeletionMode

|                |                      |
| -------------- | -------------------- |
| **Type**       | `enum (of string)`   |
| **Required**   | No                   |
| **Defined in** | #/$defs/DeletionMode |

Must be one of:
* "purge"
* "mark"

#### 4.3.2. Property `MirrorPolicy > spec > deletionMode > anyOf > item 1` {#spec_deletionMode_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

### 4.4. Property `MirrorPolicy > spec > defaults` {#spec_defaults}

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Defaults inherited by every import.

| Any of(Option)                      |
| ----------------------------------- |
| [Defaults](#spec_defaults_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i1)   |

#### 4.4.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults` {#spec_defaults_anyOf_i0}

**Title:** Defaults

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `object`         |
| **Required**              | No               |
| **Additional properties** | Not allowed      |
| **Defined in**            | #/$defs/Defaults |

| Property                                                | Pattern | Type        | Deprecated | Definition | Title/Description                             |
| ------------------------------------------------------- | ------- | ----------- | ---------- | ---------- | --------------------------------------------- |
| - [destinations](#spec_defaults_anyOf_i0_destinations ) | No      | Combination | No         | -          | Destinations                                  |
| - [transform](#spec_defaults_anyOf_i0_transform )       | No      | Combination | No         | -          | Transform                                     |
| - [archive](#spec_defaults_anyOf_i0_archive )           | No      | Combination | No         | -          | Default retention policy for every import.    |
| - [tags](#spec_defaults_anyOf_i0_tags )                 | No      | Combination | No         | -          | Default tag-selection rules for every import. |
| - [platforms](#spec_defaults_anyOf_i0_platforms )       | No      | Combination | No         | -          | Platforms                                     |
| - [owners](#spec_defaults_anyOf_i0_owners )             | No      | Combination | No         | -          | Owners                                        |
| - [vendor](#spec_defaults_anyOf_i0_vendor )             | No      | Combination | No         | -          | Vendor                                        |

##### 4.4.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations` {#spec_defaults_anyOf_i0_destinations}

**Title:** Destinations

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Default destinations for every import.

| Any of(Option)                                          |
| ------------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_destinations_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_destinations_anyOf_i1) |

###### 4.4.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0` {#spec_defaults_anyOf_i0_destinations_anyOf_i0}

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

| Each item of this array must be                                    | Description |
| ------------------------------------------------------------------ | ----------- |
| [Destination](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items) | -           |

###### 4.4.1.1.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination {#spec_defaults_anyOf_i0_destinations_anyOf_i0_items}

**Title:** Destination

|                           |                     |
| ------------------------- | ------------------- |
| **Type**                  | `object`            |
| **Required**              | No                  |
| **Additional properties** | Not allowed         |
| **Defined in**            | #/$defs/Destination |

| Property                                                                        | Pattern | Type        | Deprecated | Definition | Title/Description |
| ------------------------------------------------------------------------------- | ------- | ----------- | ---------- | ---------- | ----------------- |
| - [registry](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_registry )     | No      | Combination | No         | -          | Registry          |
| + [project](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_project )       | No      | string      | No         | -          | Project           |
| + [repository](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_repository ) | No      | string      | No         | -          | Repository        |

###### 4.4.1.1.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > registry` {#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_registry}

**Title:** Registry

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Logical registry name from the roster; may be omitted iff exactly one registry is configured.

| Any of(Option)                                                                  |
| ------------------------------------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_registry_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_registry_anyOf_i1) |

###### 4.4.1.1.1.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > registry > anyOf > item 0` {#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_registry_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.4.1.1.1.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > registry > anyOf > item 1` {#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_registry_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

###### 4.4.1.1.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > project` {#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_project}

**Title:** Project

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** Destination project / namespace.

###### 4.4.1.1.1.1.3. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 0 > Destination > repository` {#spec_defaults_anyOf_i0_destinations_anyOf_i0_items_repository}

**Title:** Repository

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** Destination repository.

###### 4.4.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > destinations > anyOf > item 1` {#spec_defaults_anyOf_i0_destinations_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.4.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform` {#spec_defaults_anyOf_i0_transform}

**Title:** Transform

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Default transform steps for every import.

| Any of(Option)                                       |
| ---------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_transform_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_transform_anyOf_i1) |

###### 4.4.1.2.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0` {#spec_defaults_anyOf_i0_transform_anyOf_i0}

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

| Each item of this array must be                                   | Description |
| ----------------------------------------------------------------- | ----------- |
| [TransformStep](#spec_defaults_anyOf_i0_transform_anyOf_i0_items) | -           |

###### 4.4.1.2.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > TransformStep {#spec_defaults_anyOf_i0_transform_anyOf_i0_items}

|                           |                       |
| ------------------------- | --------------------- |
| **Type**                  | `combining`           |
| **Required**              | No                    |
| **Additional properties** | Any type allowed      |
| **Defined in**            | #/$defs/TransformStep |

| One of(Option)                                                      |
| ------------------------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i1) |
| [item 2](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i2) |

###### 4.4.1.2.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 0` {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0}

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | No          |
| **Additional properties** | Not allowed |

| Property                                                                          | Pattern | Type   | Deprecated | Definition | Title/Description |
| --------------------------------------------------------------------------------- | ------- | ------ | ---------- | ---------- | ----------------- |
| + [injectCA](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0_injectCA ) | No      | object | No         | -          | _InjectCAParams   |

###### 4.4.1.2.1.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 0 > injectCA` {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0_injectCA}

**Title:** _InjectCAParams

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | Yes         |
| **Additional properties** | Not allowed |

| Property                                                                             | Pattern | Type            | Deprecated | Definition | Title/Description |
| ------------------------------------------------------------------------------------ | ------- | --------------- | ---------- | ---------- | ----------------- |
| + [certs](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0_injectCA_certs ) | No      | array of string | No         | -          | Certs             |

###### 4.4.1.2.1.1.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 0 > injectCA > certs` {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0_injectCA_certs}

**Title:** Certs

|              |                   |
| ------------ | ----------------- |
| **Type**     | `array of string` |
| **Required** | Yes               |

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | 1                  |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be                                                               | Description |
| --------------------------------------------------------------------------------------------- | ----------- |
| [certs items](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0_injectCA_certs_items) | -           |

###### 4.4.1.2.1.1.1.1.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 0 > injectCA > certs > certs items {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i0_injectCA_certs_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.4.1.2.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 1` {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i1}

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | No          |
| **Additional properties** | Not allowed |

| Property                                                                                                    | Pattern | Type   | Deprecated | Definition | Title/Description            |
| ----------------------------------------------------------------------------------------------------------- | ------- | ------ | ---------- | ---------- | ---------------------------- |
| + [rewritePackageSources](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i1_rewritePackageSources ) | No      | object | No         | -          | _RewritePackageSourcesParams |

###### 4.4.1.2.1.1.2.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 1 > rewritePackageSources` {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i1_rewritePackageSources}

**Title:** _RewritePackageSourcesParams

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | Yes         |
| **Additional properties** | Not allowed |

| Property                                                                                            | Pattern | Type   | Deprecated | Definition | Title/Description |
| --------------------------------------------------------------------------------------------------- | ------- | ------ | ---------- | ---------- | ----------------- |
| + [mirror](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i1_rewritePackageSources_mirror ) | No      | string | No         | -          | Mirror            |

###### 4.4.1.2.1.1.2.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 1 > rewritePackageSources > mirror` {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i1_rewritePackageSources_mirror}

**Title:** Mirror

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

| Restrictions   |   |
| -------------- | - |
| **Min length** | 1 |

###### 4.4.1.2.1.1.3. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 2` {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i2}

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | No          |
| **Additional properties** | Not allowed |

| Property                                                                                | Pattern | Type   | Deprecated | Definition | Title/Description  |
| --------------------------------------------------------------------------------------- | ------- | ------ | ---------- | ---------- | ------------------ |
| + [setTimezone](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i2_setTimezone ) | No      | object | No         | -          | _SetTimezoneParams |

###### 4.4.1.2.1.1.3.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 2 > setTimezone` {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i2_setTimezone}

**Title:** _SetTimezoneParams

|                           |             |
| ------------------------- | ----------- |
| **Type**                  | `object`    |
| **Required**              | Yes         |
| **Additional properties** | Not allowed |

| Property                                                                              | Pattern | Type   | Deprecated | Definition | Title/Description |
| ------------------------------------------------------------------------------------- | ------- | ------ | ---------- | ---------- | ----------------- |
| + [zone](#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i2_setTimezone_zone ) | No      | string | No         | -          | Zone              |

###### 4.4.1.2.1.1.3.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 0 > item 0 items > oneOf > item 2 > setTimezone > zone` {#spec_defaults_anyOf_i0_transform_anyOf_i0_items_oneOf_i2_setTimezone_zone}

**Title:** Zone

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

| Restrictions   |   |
| -------------- | - |
| **Min length** | 1 |

###### 4.4.1.2.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > transform > anyOf > item 1` {#spec_defaults_anyOf_i0_transform_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.4.1.3. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive` {#spec_defaults_anyOf_i0_archive}

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Default retention policy for every import.

| Any of(Option)                                      |
| --------------------------------------------------- |
| [Archive](#spec_defaults_anyOf_i0_archive_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_archive_anyOf_i1)  |

###### 4.4.1.3.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive` {#spec_defaults_anyOf_i0_archive_anyOf_i0}

**Title:** Archive

|                           |                 |
| ------------------------- | --------------- |
| **Type**                  | `object`        |
| **Required**              | No              |
| **Additional properties** | Not allowed     |
| **Defined in**            | #/$defs/Archive |

| Property                                                                   | Pattern | Type        | Deprecated | Definition | Title/Description |
| -------------------------------------------------------------------------- | ------- | ----------- | ---------- | ---------- | ----------------- |
| - [keep](#spec_defaults_anyOf_i0_archive_anyOf_i0_keep )                   | No      | Combination | No         | -          | Keep              |
| - [olderThanDays](#spec_defaults_anyOf_i0_archive_anyOf_i0_olderThanDays ) | No      | Combination | No         | -          | Olderthandays     |

###### 4.4.1.3.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > keep` {#spec_defaults_anyOf_i0_archive_anyOf_i0_keep}

**Title:** Keep

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Retain the N most-recently-imported tags of each stream.

| Any of(Option)                                                   |
| ---------------------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_archive_anyOf_i0_keep_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_archive_anyOf_i0_keep_anyOf_i1) |

###### 4.4.1.3.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > keep > anyOf > item 0` {#spec_defaults_anyOf_i0_archive_anyOf_i0_keep_anyOf_i0}

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |

###### 4.4.1.3.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > keep > anyOf > item 1` {#spec_defaults_anyOf_i0_archive_anyOf_i0_keep_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

###### 4.4.1.3.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > olderThanDays` {#spec_defaults_anyOf_i0_archive_anyOf_i0_olderThanDays}

**Title:** Olderthandays

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Of the surplus, only mark tags older than this many days (both conditions hold).

| Any of(Option)                                                            |
| ------------------------------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_archive_anyOf_i0_olderThanDays_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_archive_anyOf_i0_olderThanDays_anyOf_i1) |

###### 4.4.1.3.1.2.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > olderThanDays > anyOf > item 0` {#spec_defaults_anyOf_i0_archive_anyOf_i0_olderThanDays_anyOf_i0}

|              |           |
| ------------ | --------- |
| **Type**     | `integer` |
| **Required** | No        |

###### 4.4.1.3.1.2.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > Archive > olderThanDays > anyOf > item 1` {#spec_defaults_anyOf_i0_archive_anyOf_i0_olderThanDays_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

###### 4.4.1.3.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > archive > anyOf > item 1` {#spec_defaults_anyOf_i0_archive_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.4.1.4. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags` {#spec_defaults_anyOf_i0_tags}

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Default tag-selection rules for every import.

| Any of(Option)                                        |
| ----------------------------------------------------- |
| [TagSelection](#spec_defaults_anyOf_i0_tags_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_tags_anyOf_i1)       |

###### 4.4.1.4.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection` {#spec_defaults_anyOf_i0_tags_anyOf_i0}

**Title:** TagSelection

|                           |                      |
| ------------------------- | -------------------- |
| **Type**                  | `object`             |
| **Required**              | No                   |
| **Additional properties** | Not allowed          |
| **Defined in**            | #/$defs/TagSelection |

| Property                                                              | Pattern | Type            | Deprecated | Definition | Title/Description |
| --------------------------------------------------------------------- | ------- | --------------- | ---------- | ---------- | ----------------- |
| - [includeRegex](#spec_defaults_anyOf_i0_tags_anyOf_i0_includeRegex ) | No      | Combination     | No         | -          | Includeregex      |
| - [excludeRegex](#spec_defaults_anyOf_i0_tags_anyOf_i0_excludeRegex ) | No      | array of string | No         | -          | Excluderegex      |
| - [semverOnly](#spec_defaults_anyOf_i0_tags_anyOf_i0_semverOnly )     | No      | boolean         | No         | -          | Semveronly        |
| - [names](#spec_defaults_anyOf_i0_tags_anyOf_i0_names )               | No      | array of string | No         | -          | Names             |
| - [aliases](#spec_defaults_anyOf_i0_tags_anyOf_i0_aliases )           | No      | array of string | No         | -          | Aliases           |

###### 4.4.1.4.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > includeRegex` {#spec_defaults_anyOf_i0_tags_anyOf_i0_includeRegex}

**Title:** Includeregex

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Only tags matching this regex are selected (applied before excludes).

| Any of(Option)                                                        |
| --------------------------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_tags_anyOf_i0_includeRegex_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_tags_anyOf_i0_includeRegex_anyOf_i1) |

###### 4.4.1.4.1.1.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > includeRegex > anyOf > item 0` {#spec_defaults_anyOf_i0_tags_anyOf_i0_includeRegex_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.4.1.4.1.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > includeRegex > anyOf > item 1` {#spec_defaults_anyOf_i0_tags_anyOf_i0_includeRegex_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

###### 4.4.1.4.1.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > excludeRegex` {#spec_defaults_anyOf_i0_tags_anyOf_i0_excludeRegex}

**Title:** Excluderegex

|              |                   |
| ------------ | ----------------- |
| **Type**     | `array of string` |
| **Required** | No                |

**Description:** Tags matching any of these regexes are dropped.

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | N/A                |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be                                                | Description |
| ------------------------------------------------------------------------------ | ----------- |
| [excludeRegex items](#spec_defaults_anyOf_i0_tags_anyOf_i0_excludeRegex_items) | -           |

###### 4.4.1.4.1.2.1. MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > excludeRegex > excludeRegex items {#spec_defaults_anyOf_i0_tags_anyOf_i0_excludeRegex_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.4.1.4.1.3. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > semverOnly` {#spec_defaults_anyOf_i0_tags_anyOf_i0_semverOnly}

**Title:** Semveronly

|              |           |
| ------------ | --------- |
| **Type**     | `boolean` |
| **Required** | No        |
| **Default**  | `true`    |

**Description:** Keep only tags parseable as semver (drops `latest`, date tags, …).

###### 4.4.1.4.1.4. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > names` {#spec_defaults_anyOf_i0_tags_anyOf_i0_names}

**Title:** Names

|              |                   |
| ------------ | ----------------- |
| **Type**     | `array of string` |
| **Required** | No                |

**Description:** Explicit tag names to always include.

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | N/A                |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be                                  | Description |
| ---------------------------------------------------------------- | ----------- |
| [names items](#spec_defaults_anyOf_i0_tags_anyOf_i0_names_items) | -           |

###### 4.4.1.4.1.4.1. MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > names > names items {#spec_defaults_anyOf_i0_tags_anyOf_i0_names_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.4.1.4.1.5. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > aliases` {#spec_defaults_anyOf_i0_tags_anyOf_i0_aliases}

**Title:** Aliases

|              |                   |
| ------------ | ----------------- |
| **Type**     | `array of string` |
| **Required** | No                |

**Description:** Moving-tag alias templates (e.g. `{major}.{minor}`, `latest`) re-pointed every run.

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | N/A                |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be                                      | Description |
| -------------------------------------------------------------------- | ----------- |
| [aliases items](#spec_defaults_anyOf_i0_tags_anyOf_i0_aliases_items) | -           |

###### 4.4.1.4.1.5.1. MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > TagSelection > aliases > aliases items {#spec_defaults_anyOf_i0_tags_anyOf_i0_aliases_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.4.1.4.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > tags > anyOf > item 1` {#spec_defaults_anyOf_i0_tags_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.4.1.5. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > platforms` {#spec_defaults_anyOf_i0_platforms}

**Title:** Platforms

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Default platforms for every import.

| Any of(Option)                                       |
| ---------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_platforms_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_platforms_anyOf_i1) |

###### 4.4.1.5.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > platforms > anyOf > item 0` {#spec_defaults_anyOf_i0_platforms_anyOf_i0}

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

| Each item of this array must be                                  | Description |
| ---------------------------------------------------------------- | ----------- |
| [item 0 items](#spec_defaults_anyOf_i0_platforms_anyOf_i0_items) | -           |

###### 4.4.1.5.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > platforms > anyOf > item 0 > item 0 items {#spec_defaults_anyOf_i0_platforms_anyOf_i0_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.4.1.5.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > platforms > anyOf > item 1` {#spec_defaults_anyOf_i0_platforms_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.4.1.6. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > owners` {#spec_defaults_anyOf_i0_owners}

**Title:** Owners

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Default owners (Backstage entity refs) for every import.

| Any of(Option)                                    |
| ------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_owners_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_owners_anyOf_i1) |

###### 4.4.1.6.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > owners > anyOf > item 0` {#spec_defaults_anyOf_i0_owners_anyOf_i0}

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

| Each item of this array must be                               | Description |
| ------------------------------------------------------------- | ----------- |
| [item 0 items](#spec_defaults_anyOf_i0_owners_anyOf_i0_items) | -           |

###### 4.4.1.6.1.1. MirrorPolicy > spec > defaults > anyOf > Defaults > owners > anyOf > item 0 > item 0 items {#spec_defaults_anyOf_i0_owners_anyOf_i0_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.4.1.6.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > owners > anyOf > item 1` {#spec_defaults_anyOf_i0_owners_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.4.1.7. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > vendor` {#spec_defaults_anyOf_i0_vendor}

**Title:** Vendor

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Default vendor for every import, stamped as `org.opencontainers.image.vendor` (the rebuilding organization).

| Any of(Option)                                    |
| ------------------------------------------------- |
| [item 0](#spec_defaults_anyOf_i0_vendor_anyOf_i0) |
| [item 1](#spec_defaults_anyOf_i0_vendor_anyOf_i1) |

###### 4.4.1.7.1. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > vendor > anyOf > item 0` {#spec_defaults_anyOf_i0_vendor_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.4.1.7.2. Property `MirrorPolicy > spec > defaults > anyOf > Defaults > vendor > anyOf > item 1` {#spec_defaults_anyOf_i0_vendor_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

#### 4.4.2. Property `MirrorPolicy > spec > defaults > anyOf > item 1` {#spec_defaults_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

### 4.5. Property `MirrorPolicy > spec > imports` {#spec_imports}

**Title:** Imports

|              |         |
| ------------ | ------- |
| **Type**     | `array` |
| **Required** | Yes     |

**Description:** One or more import profiles (at least one).

|                      | Array restrictions |
| -------------------- | ------------------ |
| **Min items**        | 1                  |
| **Max items**        | N/A                |
| **Items unicity**    | False              |
| **Additional items** | False              |
| **Tuple validation** | See below          |

| Each item of this array must be      | Description |
| ------------------------------------ | ----------- |
| [ImportProfile](#spec_imports_items) | -           |

#### 4.5.1. MirrorPolicy > spec > imports > ImportProfile {#spec_imports_items}

**Title:** ImportProfile

|                           |                       |
| ------------------------- | --------------------- |
| **Type**                  | `object`              |
| **Required**              | No                    |
| **Additional properties** | Not allowed           |
| **Defined in**            | #/$defs/ImportProfile |

| Property                                            | Pattern | Type        | Deprecated | Definition                                                     | Title/Description                      |
| --------------------------------------------------- | ------- | ----------- | ---------- | -------------------------------------------------------------- | -------------------------------------- |
| + [name](#spec_imports_items_name )                 | No      | string      | No         | -                                                              | Name                                   |
| + [tags](#spec_imports_items_tags )                 | No      | object      | No         | Same as [TagSelection](#spec_defaults_anyOf_i0_tags_anyOf_i0 ) | TagSelection                           |
| - [destinations](#spec_imports_items_destinations ) | No      | Combination | No         | -                                                              | Destinations                           |
| - [transform](#spec_imports_items_transform )       | No      | Combination | No         | -                                                              | Transform                              |
| - [archive](#spec_imports_items_archive )           | No      | Combination | No         | -                                                              | Retention policy (overrides defaults). |
| - [platforms](#spec_imports_items_platforms )       | No      | Combination | No         | -                                                              | Platforms                              |
| - [variants](#spec_imports_items_variants )         | No      | Combination | No         | -                                                              | Variants                               |
| - [owners](#spec_imports_items_owners )             | No      | Combination | No         | -                                                              | Owners                                 |
| - [vendor](#spec_imports_items_vendor )             | No      | Combination | No         | -                                                              | Vendor                                 |

##### 4.5.1.1. Property `MirrorPolicy > spec > imports > ImportProfile > name` {#spec_imports_items_name}

**Title:** Name

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** Import name; part of the three-level policy/import/variant identity in the stamp.

##### 4.5.1.2. Property `MirrorPolicy > spec > imports > ImportProfile > tags` {#spec_imports_items_tags}

**Title:** TagSelection

|                           |                                                       |
| ------------------------- | ----------------------------------------------------- |
| **Type**                  | `object`                                              |
| **Required**              | Yes                                                   |
| **Additional properties** | Not allowed                                           |
| **Same definition as**    | [TagSelection](#spec_defaults_anyOf_i0_tags_anyOf_i0) |

**Description:** Tag-selection rules for this import.

##### 4.5.1.3. Property `MirrorPolicy > spec > imports > ImportProfile > destinations` {#spec_imports_items_destinations}

**Title:** Destinations

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Destinations (overrides defaults).

| Any of(Option)                                      |
| --------------------------------------------------- |
| [item 0](#spec_imports_items_destinations_anyOf_i0) |
| [item 1](#spec_imports_items_destinations_anyOf_i1) |

###### 4.5.1.3.1. Property `MirrorPolicy > spec > imports > ImportProfile > destinations > anyOf > item 0` {#spec_imports_items_destinations_anyOf_i0}

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

| Each item of this array must be                                | Description |
| -------------------------------------------------------------- | ----------- |
| [Destination](#spec_imports_items_destinations_anyOf_i0_items) | -           |

###### 4.5.1.3.1.1. MirrorPolicy > spec > imports > ImportProfile > destinations > anyOf > item 0 > Destination {#spec_imports_items_destinations_anyOf_i0_items}

**Title:** Destination

|                           |                                                                    |
| ------------------------- | ------------------------------------------------------------------ |
| **Type**                  | `object`                                                           |
| **Required**              | No                                                                 |
| **Additional properties** | Not allowed                                                        |
| **Same definition as**    | [Destination](#spec_defaults_anyOf_i0_destinations_anyOf_i0_items) |

###### 4.5.1.3.2. Property `MirrorPolicy > spec > imports > ImportProfile > destinations > anyOf > item 1` {#spec_imports_items_destinations_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.5.1.4. Property `MirrorPolicy > spec > imports > ImportProfile > transform` {#spec_imports_items_transform}

**Title:** Transform

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Transform steps (overrides defaults).

| Any of(Option)                                   |
| ------------------------------------------------ |
| [item 0](#spec_imports_items_transform_anyOf_i0) |
| [item 1](#spec_imports_items_transform_anyOf_i1) |

###### 4.5.1.4.1. Property `MirrorPolicy > spec > imports > ImportProfile > transform > anyOf > item 0` {#spec_imports_items_transform_anyOf_i0}

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

| Each item of this array must be                               | Description |
| ------------------------------------------------------------- | ----------- |
| [TransformStep](#spec_imports_items_transform_anyOf_i0_items) | -           |

###### 4.5.1.4.1.1. MirrorPolicy > spec > imports > ImportProfile > transform > anyOf > item 0 > TransformStep {#spec_imports_items_transform_anyOf_i0_items}

|                           |                                                                                                     |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| **Type**                  | `combining`                                                                                         |
| **Required**              | No                                                                                                  |
| **Additional properties** | Any type allowed                                                                                    |
| **Same definition as**    | [spec_defaults_anyOf_i0_transform_anyOf_i0_items](#spec_defaults_anyOf_i0_transform_anyOf_i0_items) |

###### 4.5.1.4.2. Property `MirrorPolicy > spec > imports > ImportProfile > transform > anyOf > item 1` {#spec_imports_items_transform_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.5.1.5. Property `MirrorPolicy > spec > imports > ImportProfile > archive` {#spec_imports_items_archive}

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Retention policy (overrides defaults).

| Any of(Option)                                  |
| ----------------------------------------------- |
| [Archive](#spec_imports_items_archive_anyOf_i0) |
| [item 1](#spec_imports_items_archive_anyOf_i1)  |

###### 4.5.1.5.1. Property `MirrorPolicy > spec > imports > ImportProfile > archive > anyOf > Archive` {#spec_imports_items_archive_anyOf_i0}

**Title:** Archive

|                           |                                                     |
| ------------------------- | --------------------------------------------------- |
| **Type**                  | `object`                                            |
| **Required**              | No                                                  |
| **Additional properties** | Not allowed                                         |
| **Same definition as**    | [Archive](#spec_defaults_anyOf_i0_archive_anyOf_i0) |

###### 4.5.1.5.2. Property `MirrorPolicy > spec > imports > ImportProfile > archive > anyOf > item 1` {#spec_imports_items_archive_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.5.1.6. Property `MirrorPolicy > spec > imports > ImportProfile > platforms` {#spec_imports_items_platforms}

**Title:** Platforms

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Platforms (overrides defaults).

| Any of(Option)                                   |
| ------------------------------------------------ |
| [item 0](#spec_imports_items_platforms_anyOf_i0) |
| [item 1](#spec_imports_items_platforms_anyOf_i1) |

###### 4.5.1.6.1. Property `MirrorPolicy > spec > imports > ImportProfile > platforms > anyOf > item 0` {#spec_imports_items_platforms_anyOf_i0}

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

| Each item of this array must be                              | Description |
| ------------------------------------------------------------ | ----------- |
| [item 0 items](#spec_imports_items_platforms_anyOf_i0_items) | -           |

###### 4.5.1.6.1.1. MirrorPolicy > spec > imports > ImportProfile > platforms > anyOf > item 0 > item 0 items {#spec_imports_items_platforms_anyOf_i0_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.5.1.6.2. Property `MirrorPolicy > spec > imports > ImportProfile > platforms > anyOf > item 1` {#spec_imports_items_platforms_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.5.1.7. Property `MirrorPolicy > spec > imports > ImportProfile > variants` {#spec_imports_items_variants}

**Title:** Variants

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Variants to fan this import into.

| Any of(Option)                                  |
| ----------------------------------------------- |
| [item 0](#spec_imports_items_variants_anyOf_i0) |
| [item 1](#spec_imports_items_variants_anyOf_i1) |

###### 4.5.1.7.1. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0` {#spec_imports_items_variants_anyOf_i0}

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

| Each item of this array must be                        | Description |
| ------------------------------------------------------ | ----------- |
| [Variant](#spec_imports_items_variants_anyOf_i0_items) | -           |

###### 4.5.1.7.1.1. MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant {#spec_imports_items_variants_anyOf_i0_items}

**Title:** Variant

|                           |                 |
| ------------------------- | --------------- |
| **Type**                  | `object`        |
| **Required**              | No              |
| **Additional properties** | Not allowed     |
| **Defined in**            | #/$defs/Variant |

| Property                                                              | Pattern | Type        | Deprecated | Definition | Title/Description |
| --------------------------------------------------------------------- | ------- | ----------- | ---------- | ---------- | ----------------- |
| + [name](#spec_imports_items_variants_anyOf_i0_items_name )           | No      | string      | No         | -          | Name              |
| - [suffix](#spec_imports_items_variants_anyOf_i0_items_suffix )       | No      | string      | No         | -          | Suffix            |
| - [transform](#spec_imports_items_variants_anyOf_i0_items_transform ) | No      | Combination | No         | -          | Transform         |

###### 4.5.1.7.1.1.1. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > name` {#spec_imports_items_variants_anyOf_i0_items_name}

**Title:** Name

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | Yes      |

**Description:** Variant name.

###### 4.5.1.7.1.1.2. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > suffix` {#spec_imports_items_variants_anyOf_i0_items_suffix}

**Title:** Suffix

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |
| **Default**  | `""`     |

**Description:** Tag suffix appended for this variant, e.g. `-eu`.

###### 4.5.1.7.1.1.3. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > transform` {#spec_imports_items_variants_anyOf_i0_items_transform}

**Title:** Transform

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Per-variant transform; `null` ⇒ inherit the resolved transform.

| Any of(Option)                                                           |
| ------------------------------------------------------------------------ |
| [item 0](#spec_imports_items_variants_anyOf_i0_items_transform_anyOf_i0) |
| [item 1](#spec_imports_items_variants_anyOf_i0_items_transform_anyOf_i1) |

###### 4.5.1.7.1.1.3.1. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > transform > anyOf > item 0` {#spec_imports_items_variants_anyOf_i0_items_transform_anyOf_i0}

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

| Each item of this array must be                                                       | Description |
| ------------------------------------------------------------------------------------- | ----------- |
| [TransformStep](#spec_imports_items_variants_anyOf_i0_items_transform_anyOf_i0_items) | -           |

###### 4.5.1.7.1.1.3.1.1. MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > transform > anyOf > item 0 > TransformStep {#spec_imports_items_variants_anyOf_i0_items_transform_anyOf_i0_items}

|                           |                                                                                                     |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| **Type**                  | `combining`                                                                                         |
| **Required**              | No                                                                                                  |
| **Additional properties** | Any type allowed                                                                                    |
| **Same definition as**    | [spec_defaults_anyOf_i0_transform_anyOf_i0_items](#spec_defaults_anyOf_i0_transform_anyOf_i0_items) |

###### 4.5.1.7.1.1.3.2. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 0 > Variant > transform > anyOf > item 1` {#spec_imports_items_variants_anyOf_i0_items_transform_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

###### 4.5.1.7.2. Property `MirrorPolicy > spec > imports > ImportProfile > variants > anyOf > item 1` {#spec_imports_items_variants_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.5.1.8. Property `MirrorPolicy > spec > imports > ImportProfile > owners` {#spec_imports_items_owners}

**Title:** Owners

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Owners as Backstage entity refs (stamped as `io.houba.owners`).

| Any of(Option)                                |
| --------------------------------------------- |
| [item 0](#spec_imports_items_owners_anyOf_i0) |
| [item 1](#spec_imports_items_owners_anyOf_i1) |

###### 4.5.1.8.1. Property `MirrorPolicy > spec > imports > ImportProfile > owners > anyOf > item 0` {#spec_imports_items_owners_anyOf_i0}

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

| Each item of this array must be                           | Description |
| --------------------------------------------------------- | ----------- |
| [item 0 items](#spec_imports_items_owners_anyOf_i0_items) | -           |

###### 4.5.1.8.1.1. MirrorPolicy > spec > imports > ImportProfile > owners > anyOf > item 0 > item 0 items {#spec_imports_items_owners_anyOf_i0_items}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.5.1.8.2. Property `MirrorPolicy > spec > imports > ImportProfile > owners > anyOf > item 1` {#spec_imports_items_owners_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

##### 4.5.1.9. Property `MirrorPolicy > spec > imports > ImportProfile > vendor` {#spec_imports_items_vendor}

**Title:** Vendor

|                           |                  |
| ------------------------- | ---------------- |
| **Type**                  | `combining`      |
| **Required**              | No               |
| **Additional properties** | Any type allowed |
| **Default**               | `null`           |

**Description:** Vendor (overrides defaults), stamped as `org.opencontainers.image.vendor`.

| Any of(Option)                                |
| --------------------------------------------- |
| [item 0](#spec_imports_items_vendor_anyOf_i0) |
| [item 1](#spec_imports_items_vendor_anyOf_i1) |

###### 4.5.1.9.1. Property `MirrorPolicy > spec > imports > ImportProfile > vendor > anyOf > item 0` {#spec_imports_items_vendor_anyOf_i0}

|              |          |
| ------------ | -------- |
| **Type**     | `string` |
| **Required** | No       |

###### 4.5.1.9.2. Property `MirrorPolicy > spec > imports > ImportProfile > vendor > anyOf > item 1` {#spec_imports_items_vendor_anyOf_i1}

|              |        |
| ------------ | ------ |
| **Type**     | `null` |
| **Required** | No     |

----------------------------------------------------------------------------------------------------------------------------
