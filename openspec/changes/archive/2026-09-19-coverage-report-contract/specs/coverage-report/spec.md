## Purpose

Makes the JSON report of `knock audit` a published, versioned contract that downstream tools can
consume as the inventory of placed images without pinning a knock build.

## ADDED Requirements

### Requirement: The JSON coverage report carries a version marker

When `KNOCK_LOG_FORMAT=json`, `knock audit` SHALL write one JSON document to stdout whose top level
carries `apiVersion: "knock.io/v1alpha1"` and `kind: "CoverageReport"`, alongside `registries`,
`counts` and `outcomes`.

#### Scenario: Version marker present

- **WHEN** `knock audit` runs with `KNOCK_LOG_FORMAT=json`
- **THEN** the document's `apiVersion` is `knock.io/v1alpha1` and its `kind` is `CoverageReport`

### Requirement: Changes within an apiVersion are additive only

Within one `apiVersion`, knock SHALL only add optional fields to the report. Removing or renaming a
field, changing its type, or changing its meaning SHALL change the `apiVersion`. Consumers SHALL be
able to ignore unknown fields.

#### Scenario: Existing fields are stable

- **WHEN** a consumer reads `outcomes[].image_ref`, `digest`, `covered`, `signed`, `sbom` and `policy`
  from a `knock.io/v1alpha1` report
- **THEN** they keep the meaning they had before the version marker was introduced

### Requirement: The report schema is published

The JSON Schema of the report SHALL be published at
`docs/reference/schemas/coverage-report.schema.json` with a rendered reference page. It SHALL be
derived from the report model, never hand-written, and a check SHALL fail when the committed schema
differs from the one the model produces.

#### Scenario: Emitted report validates

- **WHEN** a `knock audit` JSON report is validated against the published schema
- **THEN** it is valid

#### Scenario: Schema drift is caught

- **WHEN** the report model changes and the committed schema is not regenerated
- **THEN** the test suite fails

### Requirement: The report names the SBOM formats found

When `--sbom` is set, each covered image's outcome SHALL carry `sbom_formats`: the sorted list of
SBOM format names (`spdx-json`, `cyclonedx-json`) whose SBOM referrer was found on the image, empty
when none was found. `sbom` SHALL remain `true` exactly when `sbom_formats` is non-empty. When
`--sbom` is not set, or the image is not covered, or reading it failed, `sbom_formats` SHALL be
`null`.

#### Scenario: Both formats attached

- **WHEN** a covered image has both an SPDX and a CycloneDX SBOM referrer and `--sbom` is set
- **THEN** its outcome has `sbom: true` and `sbom_formats: ["cyclonedx-json", "spdx-json"]`

#### Scenario: No SBOM attached

- **WHEN** a covered image has no SBOM referrer and `--sbom` is set
- **THEN** its outcome has `sbom: false` and `sbom_formats: []`

#### Scenario: SBOM not probed

- **WHEN** `knock audit` runs without `--sbom`
- **THEN** every outcome has `sbom: null` and `sbom_formats: null`

### Requirement: The CLI reference documents the JSON output

The `knock audit` help text, and so the generated CLI reference page, SHALL describe the JSON
output: the version marker, the per-outcome fields, and the compatibility rule, and SHALL link the
published schema.

#### Scenario: Reference page mentions the contract

- **WHEN** the CLI reference is regenerated
- **THEN** the `knock audit` section names `apiVersion`, `sbom_formats` and the coverage-report schema
