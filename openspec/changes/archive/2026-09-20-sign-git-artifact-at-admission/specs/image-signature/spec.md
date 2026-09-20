## REMOVED Requirements

### Requirement: A policy declares admission explicitly

**Reason**: Its "Git source refuses admit" clause and scenario assert behaviour the code no longer
has — the validator is gone and a git-sourced policy now accepts `admit`. A MODIFIED block cannot
retract a scenario (archive refuses to drop one), so the requirement is removed and re-stated below
without that clause.

**Migration**: None for a policy author — the replacement below keeps the field, its `false`
default and its meaning, and only widens which sources accept it. A git-sourced policy that was
previously refused now parses; nothing that previously parsed changes behaviour.

## ADDED Requirements

### Requirement: A policy declares admission explicitly, whatever its source

The `MirrorPolicy` schema SHALL carry a boolean `spec.admit`, defaulting to `false`. `admit: true`
SHALL mean that every artifact this policy places is admitted. The system SHALL NOT refuse `admit`
on the grounds of the policy's source class. What knock signs on the git path, and in what order,
is specified by `artifact-signature`.

#### Scenario: Default is not admitted

- **WHEN** a policy omits `admit`
- **THEN** knock places and attests its images and signs none of them

#### Scenario: Git source accepts admit

- **WHEN** a policy with a git source declares `admit: true`
- **THEN** the policy parses and validates

#### Scenario: Registry source accepts admit

- **WHEN** a policy with a registry source declares `admit: true`
- **THEN** the policy parses and validates
