## ADDED Requirements

### Requirement: knock lint validates a policy tree offline

`knock lint <dir>` SHALL read every `.yml`/`.yaml` file under `<dir>`, recursively, as a MirrorPolicy,
and validate the whole tree without calling any registry, git remote, builder, signer or SBOM tool.
It SHALL be read-only: it places, deletes and annotates nothing.

#### Scenario: Valid tree, no network

- **GIVEN** a directory of valid MirrorPolicy files and no reachable registry
- **WHEN** `knock lint <dir>` runs
- **THEN** it exits 0 and reports no error

#### Scenario: Non-policy files are not read

- **GIVEN** a directory holding a `README.md` next to policy files
- **WHEN** `knock lint <dir>` runs
- **THEN** the `README.md` is neither parsed nor reported

### Requirement: A wrong path or an empty tree never passes

`knock lint` SHALL exit 3 when `<dir>` does not exist or is not a directory. It SHALL report an error,
and exit 1, when `<dir>` holds no `.yml`/`.yaml` file at all.

#### Scenario: Misspelled directory

- **GIVEN** `<dir>` does not exist
- **WHEN** `knock lint <dir>` runs
- **THEN** the command exits 3

#### Scenario: Directory without policies

- **GIVEN** `<dir>` exists and holds no `.yml`/`.yaml` file
- **WHEN** `knock lint <dir>` runs
- **THEN** the report holds one error saying no policy was found
- **AND** the command exits 1

### Requirement: Every error is collected, not only the first

`knock lint` SHALL report every error it finds across the tree in one run. An invalid file SHALL NOT
stop the validation of the other files. Each error SHALL carry the path of the file, relative to
`<dir>`, the location inside the policy when one is known, and a message.

#### Scenario: Two broken files, two errors

- **GIVEN** a tree where `a.yaml` has an unknown field and `b.yaml` is not valid YAML
- **WHEN** `knock lint <dir>` runs
- **THEN** the report holds one error for `a.yaml`, located at the unknown field, and one for `b.yaml`
- **AND** the command exits 1

### Requirement: Each file is validated against the MirrorPolicy model (N1)

Each file SHALL be validated as `knock reconcile` validates it: well-formed YAML, a mapping at the
root, the right `apiVersion` and `kind`, no unknown field, and every semantic rule of the model.

#### Scenario: Semantic rule outside the JSON Schema

- **GIVEN** a policy that the published JSON Schema accepts but a semantic rule of the model refuses
- **WHEN** `knock lint <dir>` runs
- **THEN** the report holds an error for that file naming the refused rule

#### Scenario: Same verdict as reconcile

- **GIVEN** any single policy file
- **WHEN** `knock lint` and the policy loading of `knock reconcile` read it
- **THEN** `knock lint` reports an error for it if and only if `knock reconcile` refuses to load it

### Requirement: Imports are resolved against their defaults (N2)

`knock lint` SHALL resolve `defaults` into each import of every valid policy, as `knock reconcile`
does. For every resolved `transform` and
`remediate` step, of each import and each variant, it SHALL check that the step name is a registered
step and that its parameters satisfy that step's policy model, as the reconcile plan phase does.

#### Scenario: Unknown or ill-formed transform step

- **GIVEN** an import whose `transform` declares `injectCa` (a misspelling of `injectCA`), or a known
  step with a parameter its model refuses
- **WHEN** `knock lint <dir>` runs
- **THEN** the report holds an error for that import naming the step
- **AND** no configuration is needed to find it

#### Scenario: Import valid only once defaults are merged

- **GIVEN** an import that omits a field its policy's `defaults` provides
- **WHEN** `knock lint <dir>` runs
- **THEN** no error is reported for that import

### Requirement: Each destination repository is owned by one policy (N2)

As `knock reconcile` does, `knock lint` SHALL report an error when two policies with different
`metadata.name` write into the same destination repository, naming the repository and both files.
Without configuration, the destination repository SHALL be identified by its logical registry name,
project and repository; with configuration, by the resolved registry host, project and repository.

#### Scenario: Two policies, one repository

- **GIVEN** `a.yaml` and `b.yaml` are two policies that both write into `harbor/lib/nginx`
- **WHEN** `knock lint <dir>` runs
- **THEN** the report holds an error naming `harbor/lib/nginx`, `a.yaml` and `b.yaml`
- **AND** the command exits 1

#### Scenario: Two imports of one policy, one repository

- **GIVEN** one policy whose two imports both write into `harbor/lib/nginx`
- **WHEN** `knock lint <dir>` runs
- **THEN** no ownership error is reported for that repository

### Requirement: Alias overlaps between imports of one policy (N2)

An alias is **literal** when it holds no `{…}` placeholder. When two imports of the same policy write
the same literal alias into the same destination repository, `knock lint` SHALL report an error naming
both imports. When two imports of the same policy write alias templates with placeholders into the same
destination repository, `knock lint` SHALL report a warning naming both imports, since whether they
collide depends on upstream tags it does not read. Imports of different policies are not compared:
sharing a repository is already an ownership error.

#### Scenario: Same literal alias, same repository

- **GIVEN** one policy whose imports `v1` and `v2` both write the alias `latest` into `harbor/lib/nginx`
- **WHEN** `knock lint <dir>` runs
- **THEN** the report holds an error naming both imports
- **AND** the command exits 1

#### Scenario: Overlapping templates, same repository

- **GIVEN** one policy whose imports `v1` and `v2` both write the alias template `{major}` into
  `harbor/lib/nginx`
- **WHEN** `knock lint <dir>` runs
- **THEN** the report holds a warning naming both imports, and no error for them
- **AND** the command exits 0 when nothing else is wrong

#### Scenario: Same alias, different repositories

- **GIVEN** one policy whose import `v1` writes `latest` into `harbor/lib/nginx` and import `v2` writes
  `latest` into `harbor/lib/redis`
- **WHEN** `knock lint <dir>` runs
- **THEN** no error and no warning is reported for that alias

### Requirement: Configuration references are checked when configuration is present (N3)

When `KNOCK_REGISTRIES` is set, `knock lint` SHALL check every reference a policy makes to the
configuration: the destination registry, each `caCert` and each package mirror. It SHALL report an
error for each name the configuration does not hold, and for each CA file it cannot read. When
`KNOCK_REGISTRIES` is not set, `knock lint` SHALL skip these checks, record the skip in the report, and
not fail because of it.

#### Scenario: Unknown destination registry

- **GIVEN** `KNOCK_REGISTRIES` holds only `harbor`, and a policy targets the registry `quay`
- **WHEN** `knock lint <dir>` runs
- **THEN** the report holds an error for that policy naming `quay` and the configured registries

#### Scenario: No configuration

- **GIVEN** `KNOCK_REGISTRIES` is not set, and a policy targets the registry `quay`
- **WHEN** `knock lint <dir>` runs
- **THEN** no error is reported for `quay`
- **AND** the report lists the configuration checks as skipped

#### Scenario: The skip is visible in text output

- **GIVEN** `KNOCK_REGISTRIES` is not set and `KNOCK_LOG_FORMAT` is `text`
- **WHEN** `knock lint <dir>` runs
- **THEN** the first line of its output says the configuration checks were skipped

### Requirement: The report follows KNOCK_LOG_FORMAT and its schema is published

When `KNOCK_LOG_FORMAT=json`, `knock lint` SHALL write one JSON document to stdout carrying
`apiVersion: "knock.io/v1alpha1"`, `kind: "LintReport"`, and the lists `errors`, `warnings` and
`skipped`. Otherwise it SHALL write the same findings as text, for a person to read, as `knock audit`
does. The JSON Schema of the report SHALL be published under
`docs/reference/schemas/`, derived from the report model, and a check SHALL fail when the committed
schema differs from the one the model produces. Within one `apiVersion`, changes SHALL be additive
only.

#### Scenario: Report validates against its schema

- **GIVEN** `KNOCK_LOG_FORMAT=json`
- **WHEN** `knock lint <dir>` runs on any tree
- **THEN** its stdout validates against the published lint report schema

### Requirement: The exit code says whether the tree may be merged

`knock lint` SHALL exit 0 when the report holds no error, whatever its warnings and skips; 1 when it
holds at least one error; and 3 when the configuration it was given cannot be read.

#### Scenario: Warnings only

- **GIVEN** a tree whose only finding is a warning
- **WHEN** `knock lint <dir>` runs
- **THEN** the command exits 0

#### Scenario: Unreadable configuration

- **GIVEN** `KNOCK_REGISTRIES` is set to a value that is not valid JSON
- **WHEN** `knock lint <dir>` runs
- **THEN** the command exits 3

### Requirement: reconcile keeps failing on the first invalid policy

Introducing `knock lint` SHALL NOT change how `knock reconcile` and `knock promote` load policies:
they SHALL still stop at the first invalid file, before any mutation.

#### Scenario: reconcile on a broken tree

- **GIVEN** a tree where `a.yaml` and `b.yaml` are both invalid
- **WHEN** `knock reconcile <dir>` runs
- **THEN** it fails on the first of them, as before, and places nothing
