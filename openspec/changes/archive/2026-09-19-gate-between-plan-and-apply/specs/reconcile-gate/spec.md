## ADDED Requirements

### Requirement: reconcile writes its plan without placing anything

`knock reconcile <dir> --plan-out <file>` SHALL mutate nothing and SHALL write a `ReconcilePlan`
document listing every import, update and rebuild the run would perform. Each entry SHALL carry the
policy, the kind (`import` / `update` / `rebuild`), the destination repository and tag, and the
source repository, tag and digest. An update caused by a transform change SHALL be `rebuild`.

#### Scenario: New tag is planned as an import

- **WHEN** a policy selects a tag absent from its destination and the run uses `--plan-out`
- **THEN** the plan holds one `import` entry with the source digest, and nothing is copied

#### Scenario: Changed transforms are planned as rebuilds

- **WHEN** a placed tag's recorded transform version differs from the policy's
- **THEN** its plan entry has kind `rebuild`

### Requirement: reconcile applies only what a filtered plan approves

`knock reconcile <dir> --apply-plan <file>` SHALL apply an import, update or rebuild only when the
file holds an entry with the same policy, destination, tag, kind and source digest. Every other
import, update or rebuild SHALL be reported as `withheld` and SHALL NOT be applied. A withheld
operation SHALL leave the destination tag as it was. Deletions, retention marks and coverage
backfills SHALL run as in `reconcile`. An alias whose target is a withheld import SHALL NOT be moved.

#### Scenario: Refused update keeps the version in service

- **WHEN** the upstream digest of a placed tag moved and the filtered plan omits its `update`
- **THEN** the tag is not copied, not deleted, and reported `withheld`

#### Scenario: Upstream moved after the plan was written

- **WHEN** the filtered plan approves an import for digest A and the live source digest is now B
- **THEN** the import is withheld

#### Scenario: Refused import does not move the alias

- **WHEN** the filtered plan omits the import of the highest tag, which a floating alias targets
- **THEN** neither the tag nor the alias is written

### Requirement: under the gate, only approved placements are signed

With `--apply-plan`, a policy with `admit: true` SHALL sign an image only when an approved operation
placed it. The attestation backfill on an already placed digest SHALL attest without signing.
Without `--apply-plan`, `admit: true` SHALL keep its existing meaning.

#### Scenario: Approved import of an admitted policy is signed

- **WHEN** an `admit: true` policy's import is approved by the filtered plan
- **THEN** the placed digest is attested and signed

#### Scenario: Backfill under the gate attests without signing

- **WHEN** an `admit: true` policy's kept tag lacks its attestation and the run uses `--apply-plan`
- **THEN** the digest is attested and not signed

### Requirement: the two gate options are exclusive

`--plan-out` and `--apply-plan` together SHALL be refused with a `ConfigError` (exit 3). An
unreadable or schema-invalid plan file SHALL be refused with a `ConfigError` before anything is
placed.

#### Scenario: Invalid plan file

- **WHEN** `--apply-plan` names a file whose entry has an unknown kind
- **THEN** the command exits 3 and places nothing
