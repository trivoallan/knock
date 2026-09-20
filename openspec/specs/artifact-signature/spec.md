# artifact-signature Specification

## Purpose
Admission signing for a standalone OCI artifact — one placed from a git source rather than built or
copied as an image. It says when knock signs such an artifact, what digest the signature lands on,
and how a run stays idempotent so turning admission on backfills an existing mirror exactly once.

## Requirements

### Requirement: A git-sourced policy can declare admission

A policy whose source is a git repository SHALL accept `spec.admit`, with the same meaning and the
same `false` default as on a registry source: `admit: true` declares that every artifact this
policy places is admitted. The system SHALL NOT refuse `admit` on a git source.

#### Scenario: Git source accepts admit

- **WHEN** a policy with a git source declares `admit: true`
- **THEN** the policy parses and validates

#### Scenario: Default is not admitted

- **WHEN** a git-sourced policy omits `admit`
- **THEN** knock places and stamps its artifacts and signs none of them

### Requirement: knock signs an admitted artifact before its alias designates it

When a git-sourced policy is `admit: true` and knock places a revision, the system SHALL sign the
placed artifact's digest with the configured signer, and SHALL do so before it moves the ref-name
alias onto that digest. A signing failure SHALL fail the operation, and the alias SHALL NOT be
moved. The signature SHALL be placed on the digest, not on a tag, so it survives the alias moving
away later.

#### Scenario: Admitted placement is signed, then aliased

- **WHEN** an `admit: true` git policy places a new revision
- **THEN** the artifact's digest is signed, and only then does the ref-name alias designate it

#### Scenario: Signing failure leaves the alias where it was

- **WHEN** signing the placed digest fails
- **THEN** the operation fails, the alias still designates whatever it designated before, and the
  policy's other destinations are unaffected

#### Scenario: Non-admitted placement is stamped but not signed

- **WHEN** an `admit: false` git policy places a new revision
- **THEN** the artifact is stamped and never signed

### Requirement: Admission backfills an existing mirror exactly once

When a git-sourced policy is `admit: true` and the revision it declares is already placed, the
system SHALL sign that digest if and only if it does not already carry a signature. Turning `admit`
on SHALL therefore sign the already-placed artifacts on the next run, and a run over an already
admitted, already converged mirror SHALL place no second signature.

#### Scenario: Turning admit on signs what is already placed

- **WHEN** a policy whose revisions are all already placed is reconciled with `admit: true` for the
  first time
- **THEN** each placed digest that carries no signature is signed

#### Scenario: Steady state signs nothing twice

- **WHEN** an `admit: true` git policy is reconciled and every declared revision is placed and
  already signed
- **THEN** no signing call is made

#### Scenario: A stale alias alone does not re-sign

- **WHEN** the declared revision is placed and signed but the ref-name alias designates an older
  revision
- **THEN** the alias is repointed and the digest is not signed again

### Requirement: Admission without a signer is refused before anything is placed

When a git-sourced policy declares `admit: true` and no signer is configured, the system SHALL fail
the run with a configuration error (exit 3) during the plan phase, before any artifact is fetched
or placed. It SHALL NOT place artifacts and leave them unsigned.

#### Scenario: Admit without a signer fails at plan time

- **WHEN** an `admit: true` git policy is reconciled with no signer configured
- **THEN** the run exits 3 and nothing is fetched, placed or aliased

### Requirement: A placed artifact's signature is never removed

The system SHALL NOT delete the signature of a placed artifact. Setting a git-sourced policy from
`admit: true` back to `false` SHALL stop new signatures without removing existing ones.

#### Scenario: Revoking admit removes nothing

- **WHEN** a git policy that previously signed its artifacts is reconciled with `admit: false`
- **THEN** no referrer is deleted and no signing call is made

### Requirement: A signed artifact satisfies the image-signature gate

An artifact signed under this capability SHALL satisfy `knock verify --require image-signature` on
its digest, and on the ref-name alias for as long as that alias designates it. The gate SHALL NOT
require the artifact to be an image.

#### Scenario: Placed skill passes the signature gate

- **WHEN** `knock verify --require image-signature` names a skill placed by an `admit: true` policy
- **THEN** the gate exits 0

#### Scenario: Unsigned skill fails the signature gate

- **WHEN** `knock verify --require image-signature` names a skill placed by an `admit: false` policy
- **THEN** the gate exits 1
