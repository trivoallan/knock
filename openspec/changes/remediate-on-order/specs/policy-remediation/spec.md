# Spec Delta

## Purpose

Separates, in a knock policy, the transform applied to every placed image from the remediation applied only on order, per plan operation, without knock knowing who gave the order or why.

## ADDED Requirements

### Requirement: Two step lists in a policy
A policy SHALL accept two step lists at the `defaults`, import and variant levels: `transform:` and
`remediate:`. Each list SHALL resolve on its own with the inheritance `transform:` has today (a
variant replaces its import, an import replaces `defaults`). `transform:` MUST accept `injectCA`,
`rewritePackageSources` and `setTimezone`, and MUST refuse `upgradePackages`. `remediate:` MUST
accept `upgradePackages` and `rewritePackageSources`, and refuse every other step. A non-rebuildable
`artifactType` MUST refuse `remediate:` as it refuses `transform:`. The published `MirrorPolicy`
JSON Schema MUST describe both lists.

#### Scenario: Split policy is valid
- **WHEN** an import declares `transform: [injectCA, rewritePackageSources]` and
  `remediate: [upgradePackages: {}]`
- **THEN** validation accepts it

#### Scenario: Remediation declared as a transform
- **WHEN** a policy declares `upgradePackages` under `transform:`
- **THEN** validation refuses it with a message naming `remediate:`, and nothing is placed

#### Scenario: Transform declared as a remediation
- **WHEN** a policy declares `setTimezone` under `remediate:`
- **THEN** validation refuses it

### Requirement: `upgradePackages` takes no epoch
`upgradePackages` MUST accept no parameter; an `epoch` declared in a policy MUST be refused at
validation. A remediation with `upgradePackages` MUST require `rewritePackageSources` in the same
operation's resolved transform, or earlier in its resolved remediation, so the upgrade goes through
the internal mirror.

#### Scenario: Former epoch in the policy
- **WHEN** a policy declares `upgradePackages: { epoch: "1" }`
- **THEN** validation refuses it, and the message says the epoch now comes from the remediation order

#### Scenario: Remediation without a mirror
- **WHEN** an import declares `remediate: [upgradePackages: {}]` with no `rewritePackageSources`
  in its resolved transform nor before it in its remediation
- **THEN** validation refuses it

### Requirement: The plan carries remediation orders
A `ReconcilePlan` operation SHALL accept an optional `remediate` field holding an `epoch` (1 to 64
characters of `[A-Za-z0-9._-]`). `reconcile --plan-out` MUST NOT write it. The field MUST NOT be
part of the operation's key: an approval stays bound to (policy, destination, tag, kind, source
digest). Under `--apply-plan`, an approved operation carrying `remediate` MUST be built with the
resolved transform then the resolved remediation, in that order, the epoch written into the
remediation step. An approved operation without `remediate` MUST be applied with no remediation
step. An epoch outside the alphabet MUST make `--apply-plan` refuse the plan file before any write.

#### Scenario: Order on an operation
- **WHEN** the approved plan carries `remediate: {epoch: "20261016T020000Z"}` on an `import` of an
  import that declares `remediate:`
- **THEN** the image is built with transform then remediation, and the epoch is in its provenance

#### Scenario: No order
- **WHEN** the approved plan carries no `remediate` on an operation of an import that declares
  `remediate:`
- **THEN** the operation is applied as if `remediate:` did not exist

#### Scenario: Order on an import without remediation
- **WHEN** the plan carries `remediate` on an operation whose import declares no `remediate:` step
- **THEN** the operation is withheld with the reason `remediation-undeclared`, and the destination
  is left as it was

#### Scenario: Unsafe epoch
- **WHEN** the plan carries `remediate: {epoch: "x; rm -rf /"}`
- **THEN** `--apply-plan` refuses the file, exits non-zero and places nothing

### Requirement: A copy-only import can be remediated
An import with no resolved transform but a declared remediation SHALL accept a remediation order:
the operation is then built instead of copied.

#### Scenario: Copy becomes a build
- **WHEN** an import without `transform:` declares
  `remediate: [rewritePackageSources: {mirror: internal}, upgradePackages: {}]` and receives an order
- **THEN** the operation is built with those two steps; without an order the same operation is
  copied as is

### Requirement: Only remediations are staged
Under `--stage-to`, an operation SHALL be held in the staging registry if and only if it carries a
remediation order. A transform-only rebuild MUST be placed at its destination, as without
`--stage-to`. Without `--stage-to`, an operation carrying an order MUST be withheld with the reason
`remediation-unstaged`. `StagedRebuilds` entries MUST carry the order's epoch.

#### Scenario: Transform only under staging
- **WHEN** `--apply-plan --stage-to transit` applies a rebuild with no remediation order
- **THEN** the image is placed at its destination and is absent from `StagedRebuilds`

#### Scenario: Order without staging
- **WHEN** `--apply-plan` receives an operation carrying an order without `--stage-to`
- **THEN** the operation is withheld with the reason `remediation-unstaged`, nothing is pushed for
  it, and the plan's other operations are applied

#### Scenario: Remediation under staging
- **WHEN** `--apply-plan --stage-to transit` applies an operation carrying an order
- **THEN** the image is held in staging, not signed as admitted, and listed in `StagedRebuilds`

### Requirement: A remediation survives the next pass
The stamp and the transform attestation SHALL record the applied remediation apart from the transform
version: the attestation predicate `/v1` gains an optional `remediation {steps, epoch}` field and
`steps[]` stays the transform alone. `reconcile` MUST compute drift on the transform version alone:
a remediated image whose transform and source did not change MUST NOT be planned again. When an
operation is planned onto a remediated destination, the plan MUST say so with an informative
`remediated: true` field, outside the key.

#### Scenario: Next pass with no change
- **WHEN** a remediated image is in place and neither its source nor its transform moved
- **THEN** the next pass plans nothing for that tag

#### Scenario: Remediated copy-only import
- **WHEN** a copy-only import's tag was remediated
- **THEN** the placed image carries no transform version annotation and is not planned again

#### Scenario: Transform changed on a remediated image
- **WHEN** an import's transform changes and one of its tags is remediated
- **THEN** that tag's `rebuild` operation carries `remediated: true`

### Requirement: Applied operations are reported
`reconcile --apply-plan --applied-out <file>` SHALL write, for every operation applied or held in
staging, its source digest and the digest written (at the destination or in staging), and for every
withheld operation, its source digest and the reason, in an `AppliedOperations` document whose JSON
Schema is derived from the model and published.

#### Scenario: Transform-only rebuild placed
- **WHEN** a transform-only rebuild is placed
- **THEN** the document links its source digest to the placed digest

#### Scenario: Withheld order reported
- **WHEN** an operation carrying an order is withheld because its import declares no remediation
- **THEN** the document lists it with its source digest and the reason `remediation-undeclared`
