# Spec Delta

## Purpose

Lets an external evaluator judge the image a rebuild produced before that image reaches its destination: rebuilt images are held in a staging registry, listed in a file, and placed only when a filtered copy of that file still names them.

## ADDED Requirements

### Requirement: Building operations are staged instead of placed

`knock reconcile <dir> --apply-plan <plan> --stage-to <registry> --staged-out <file>` SHALL push
every approved operation that builds an image to the staging registry instead of its destination.
The staged image SHALL carry the same stamp, SBOM referrers and signed attestations it would carry
in the destination, and SHALL NOT be signed as admitted. The destination tag SHALL be left exactly
as it was. Approved operations on the copy path, deletions, retention marks and backfills SHALL run
as they do without staging.

#### Scenario: Approved import with transforms is staged

- **WHEN** an approved `import` of a policy with a `transform` list runs with `--stage-to`
- **THEN** the rebuilt image is in the staging registry with its stamp and attestations, the destination repository has no such tag, and the operation is reported as `staged`

#### Scenario: Rebuild of a placed tag leaves it in service

- **WHEN** an approved `rebuild` of a tag already in the destination runs with `--stage-to`
- **THEN** the destination tag still resolves to the digest it had before the run

#### Scenario: Copy-path import is placed directly

- **WHEN** an approved `import` of a policy without transforms runs with `--stage-to`
- **THEN** the image is copied to its destination as it is today and no staged entry is written for it

#### Scenario: Dry run stages nothing

- **WHEN** the run uses `--stage-to` while tag dry-run is enabled
- **THEN** nothing is pushed to the staging registry and the staged rebuilds file is written with no entries

#### Scenario: Staged image of an admitting policy is not signed

- **WHEN** an approved operation of an `admit: true` policy is staged
- **THEN** its attestations are signed and the image itself carries no admission signature

### Requirement: An alias never moves onto a staged tag

During a run with `--stage-to`, an alias whose target tag was staged in that run and is absent from
the destination SHALL NOT be written. An alias whose target is already in the destination SHALL
keep its current target.

#### Scenario: Highest tag is staged

- **WHEN** the highest selected tag is a new import that the run stages, and a floating alias targets the highest tag
- **THEN** the alias is not moved by the run

### Requirement: The run writes the staged rebuilds file

The run SHALL write a `StagedRebuilds` document to `--staged-out` listing one entry per staged
image. Each entry SHALL carry the policy, the import and variant names, the operation kind, the
destination repository and tag, the source repository, tag and digest, and the staged repository
and digest, and the aliases whose target is that tag under the rule `reconcile` applies. A run that
staged nothing SHALL write a valid document with no entries. An operation that failed to build, to
be stamped or to be attested SHALL have no entry. The document SHALL validate against a published
JSON Schema.

#### Scenario: Two rebuilds, one build failure

- **WHEN** a run stages one image successfully and a second build fails
- **THEN** the file holds exactly one entry, the failed operation is reported as failed, and the run exits non-zero

#### Scenario: Attestation fails after the push

- **WHEN** an image is pushed to the staging registry and its attestation then fails
- **THEN** the operation is reported as failed and the file holds no entry for it

#### Scenario: Entry of the highest tag records its alias

- **WHEN** the staged tag is the one a `{major}.{minor}` alias designates
- **THEN** its entry lists that alias

#### Scenario: Nothing to stage

- **WHEN** the approved plan holds only copy-path operations
- **THEN** the file is written with an empty list of entries

### Requirement: Staging options are refused when incomplete

`--stage-to` and `--staged-out` SHALL be accepted only together and only with `--apply-plan`. Any
other combination, or a `--stage-to` name absent from the configured registry roster, SHALL be
refused with a `ConfigError` (exit 3) before anything is built, placed or deleted.

#### Scenario: Staging without a plan

- **WHEN** `reconcile` is called with `--stage-to` and `--staged-out` but without `--apply-plan`
- **THEN** the command exits 3 and nothing is built

#### Scenario: Unknown staging registry

- **WHEN** `--stage-to` names a registry that the configuration does not list
- **THEN** the command exits 3 and nothing is built

### Requirement: promote places exactly what the filtered file names

`knock promote <dir> --staged <file>` SHALL, for each entry of the file, copy the staged digest and
its referrers to the entry's destination repository, verify them there, and only then write the
destination tag. It SHALL NOT place anything for a staged image the file does not name. The digest
in the destination SHALL equal the staged digest. The verification at the destination SHALL require
the SBOM referrers and, when a signer is configured, a valid signed attestation on that digest.
When the entry's policy sets `admit: true`, the promoted image SHALL be signed. A promoted entry
SHALL be reported as `imported` when its kind is `import` and as `updated` when its kind is `update`
or `rebuild`. Promoting an entry whose destination tag already resolves to the staged digest SHALL
succeed without changing anything.

#### Scenario: Entry kept in the file

- **WHEN** the file names a staged import and that staged digest is still in the staging registry
- **THEN** the destination tag resolves to the staged digest, its SBOM and attestations are attached in the destination, and the operation is reported as `imported`

#### Scenario: Entry removed from the file

- **WHEN** an evaluator removed an entry before `promote` runs
- **THEN** nothing is written to that entry's destination and the staging registry is left untouched

#### Scenario: Admitting policy

- **WHEN** a promoted entry belongs to an `admit: true` policy
- **THEN** the image is signed in the destination after the copy

#### Scenario: Promotion run twice

- **WHEN** `promote` runs a second time on the same file after a complete first run
- **THEN** it exits 0 and the destination is unchanged

#### Scenario: No signer configured

- **WHEN** no signer is configured and the staged image carries its SBOM referrers
- **THEN** the entry is promoted once those referrers are found at the destination

#### Scenario: Planned rebuild is reported as an update

- **WHEN** an entry of kind `rebuild` is promoted
- **THEN** the operation is reported as `updated`

#### Scenario: Empty file

- **WHEN** the file holds no entries
- **THEN** `promote` places nothing and exits 0

### Requirement: promote moves aliases after placing

After placing an entry, `promote` SHALL write the aliases that entry records, each pointing to the
promoted tag. It SHALL compute no alias target itself: the rule `reconcile` applies stays the only
one. An alias recorded by an entry that was removed from the file SHALL NOT be written.

#### Scenario: Promoted tag becomes the alias target

- **WHEN** `promote` places the highest tag of an import that declares a `{major}.{minor}` alias
- **THEN** the alias resolves to the promoted digest

#### Scenario: Refused tag does not become the alias target

- **WHEN** the entry of the highest tag was removed from the file and a lower tag is in the destination
- **THEN** the alias keeps pointing to the lower tag, and promoting other entries does not move it

### Requirement: promote refuses an entry it cannot trust

`promote` SHALL fail an entry, writing no tag for it, when any of these holds: its policy is not
found under `<dir>`; its destination is not a destination that policy declares for that import; its
staged repository is not that destination re-rooted under a registry of the configured roster; the
staged reference no longer resolves to the entry's staged digest; the staged image's stamp does not
name the entry's policy, import, variant and source digest; the referrers or the signed attestation
are not found at the destination after the copy; or the entry records an alias its policy does not
declare. A failed entry SHALL NOT
prevent the other entries from being promoted, and SHALL make the command exit non-zero. A file
that is unreadable or does not validate SHALL be refused with a `ConfigError` (exit 3) before
anything is placed.

#### Scenario: Staged digest changed

- **WHEN** the staged reference of an entry now resolves to another digest
- **THEN** that entry fails naming both digests, its destination is left as it was, and the other entries are promoted

#### Scenario: Staged image gone

- **WHEN** the staging registry no longer holds an entry's digest
- **THEN** that entry fails and its destination is left as it was

#### Scenario: Destination not declared by the policy

- **WHEN** an entry names a destination repository that its policy does not declare
- **THEN** that entry fails and nothing is written to that repository

#### Scenario: Staged reference outside the staging registry

- **WHEN** an entry's staged repository points to a registry or path other than its destination re-rooted under a roster registry
- **THEN** that entry fails and nothing is copied

#### Scenario: Stamp names another policy

- **WHEN** the staged image's stamp names a policy, import, variant or source digest that differs from the entry
- **THEN** that entry fails and nothing is copied

#### Scenario: Referrers lost by the copy

- **WHEN** the digest reaches the destination without its SBOM referrers or its signed attestation
- **THEN** that entry fails and its destination tag is not written

#### Scenario: Undeclared alias

- **WHEN** an entry records an alias that its policy does not declare
- **THEN** that entry fails and neither its tag nor the alias is written

#### Scenario: Invalid file

- **WHEN** `--staged` names a file with an unknown field or kind
- **THEN** the command exits 3 and places nothing

### Requirement: An unpromoted operation is planned again

A staged image that was never promoted SHALL leave no trace in the destination, so the next
`reconcile` SHALL plan the same operation again from the live source.

#### Scenario: Refused rebuild on the next pass

- **WHEN** a staged import was removed from the file and a later `reconcile --plan-out` runs
- **THEN** the plan holds that `import` again
