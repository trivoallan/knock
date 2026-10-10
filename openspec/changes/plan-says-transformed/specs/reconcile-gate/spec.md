## MODIFIED Requirements

### Requirement: reconcile writes its plan without placing anything

`knock reconcile <dir> --plan-out <file>` SHALL mutate nothing and SHALL write a `ReconcilePlan`
document listing every import, update and rebuild the run would perform. Each entry SHALL carry the
policy, the kind (`import` / `update` / `rebuild`), the destination repository and tag, and the
source repository, tag and digest. An update caused by a transform change SHALL be `rebuild`.
Each entry SHALL also say, as `transformed`, whether applying it builds an image (the policy
resolves a transform onto the operation) or copies the source. `transformed` SHALL NOT be part of
what binds an approval: a filtered plan that omits or changes it still applies the operation.

#### Scenario: New tag is planned as an import

- **WHEN** a policy selects a tag absent from its destination and the run uses `--plan-out`
- **THEN** the plan holds one `import` entry with the source digest, and nothing is copied

#### Scenario: Changed transforms are planned as rebuilds

- **WHEN** a placed tag's recorded transform version differs from the policy's
- **THEN** its plan entry has kind `rebuild`

#### Scenario: An operation that builds says so

- **WHEN** a policy declares a transform for an import and the run uses `--plan-out`
- **THEN** the entry carries `transformed: true`

#### Scenario: A copy says so

- **WHEN** a policy declares no transform for an import and the run uses `--plan-out`
- **THEN** the entry carries `transformed: false`

#### Scenario: A filtered plan without the field still applies

- **WHEN** `--apply-plan` reads an entry with no `transformed` key for an operation that builds
- **THEN** the operation is applied
